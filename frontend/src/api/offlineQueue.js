// Offline write queue (IndexedDB-backed).
//
// Purpose: when an operator hand-keys shift/delivery/bale/fuel data and the
// network is down, we must not lose it on a Wi-Fi blip. Mutations that fail
// due to a NETWORK error (fetch throws / offline) are persisted here and
// replayed automatically when connectivity returns.
//
// IMPORTANT scope: this only ever holds writes that failed because of the
// network. A 4xx/5xx server *response* is NOT a network failure and is never
// queued — those surface to the user exactly as before. See client.js.
//
// Hand-rolled minimal IndexedDB wrapper to avoid adding a dependency.

const DB_NAME = 'fmp-offline'
const DB_VERSION = 1
const STORE = 'queue'

// Marker placed on the optimistic resolution value so the UI can distinguish a
// "saved offline, will sync" outcome from a real server response.
export const OFFLINE_QUEUED = '__fmp_offline_queued__'

let dbPromise = null

function openDB() {
  if (dbPromise) return dbPromise
  dbPromise = new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB unavailable'))
      return
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        // keyPath = client-generated UUID (also our idempotency key).
        db.createObjectStore(STORE, { keyPath: 'id' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
  return dbPromise
}

function tx(db, mode) {
  return db.transaction(STORE, mode).objectStore(STORE)
}

function reqToPromise(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

// Crypto-strong UUID where available; safe fallback otherwise.
export function makeId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

// Subscribers (e.g. the topbar badge) are notified whenever the queue length
// might have changed.
const listeners = new Set()
export function onQueueChange(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
async function notify() {
  let count = 0
  try { count = await queueCount() } catch { /* ignore */ }
  listeners.forEach((fn) => { try { fn(count) } catch { /* ignore */ } })
}

// Enqueue a failed mutation. `record` carries everything needed to replay:
//   { kind, path, method, body }  — id + created_at are added here.
export async function enqueue(record) {
  const db = await openDB()
  const item = {
    id: makeId(),
    created_at: new Date().toISOString(),
    ...record,
  }
  await reqToPromise(tx(db, 'readwrite').add(item))
  await notify()
  return item
}

export async function queueCount() {
  const db = await openDB()
  return reqToPromise(tx(db, 'readonly').count())
}

export async function getAll() {
  const db = await openDB()
  return reqToPromise(tx(db, 'readonly').getAll())
}

export async function remove(id) {
  const db = await openDB()
  await reqToPromise(tx(db, 'readwrite').delete(id))
  await notify()
}

// ---- Flush ----------------------------------------------------------------
//
// `doRequest` is injected by client.js (its internal request() helper) so this
// module stays free of fetch/token concerns. It must throw a typed error:
//   - NetworkError  → leave item queued, stop draining (still offline)
//   - HttpError(409)→ duplicate; item already synced → drop it
//   - HttpError(2xx is success, returns value)
//   - other HttpError(4xx/5xx) → server rejected the payload permanently;
//       drop it so it doesn't wedge the queue forever (and report it).

let flushing = false

export async function flushQueue(doRequest, { onSynced } = {}) {
  if (flushing) return { synced: 0, failed: 0, remaining: await safeCount() }
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    return { synced: 0, failed: 0, remaining: await safeCount() }
  }
  flushing = true
  let synced = 0
  let failed = 0
  try {
    const items = await getAll()
    // Oldest first.
    items.sort((a, b) => (a.created_at < b.created_at ? -1 : 1))
    for (const item of items) {
      try {
        await doRequest(item)
        await remove(item.id)
        synced++
      } catch (err) {
        if (err && err.isNetworkError) {
          // Still offline / connection dropped mid-drain. Keep the rest queued
          // and stop — we'll retry on the next trigger.
          break
        }
        if (err && err.status === 409) {
          // Duplicate: the server already has this (idempotency via unique
          // key, e.g. shift date+shift). Treat as synced and drop it.
          await remove(item.id)
          synced++
          continue
        }
        // Permanent server rejection (other 4xx/5xx). Drop so it can't wedge
        // the queue forever; count as failed for reporting.
        await remove(item.id)
        failed++
      }
    }
  } finally {
    flushing = false
  }
  if (synced > 0 && typeof onSynced === 'function') {
    try { onSynced(synced, failed) } catch { /* ignore */ }
  }
  return { synced, failed, remaining: await safeCount() }
}

async function safeCount() {
  try { return await queueCount() } catch { return 0 }
}
