import { useState, useEffect, useCallback, useRef } from 'react'
import { syncOfflineQueue, onQueueChange, queueCount } from '../api/client'
import { useToast } from '../context/ToastContext'

// Topbar offline/sync indicator.
//
//  - Shows an "Offline" pill when navigator.onLine is false.
//  - Shows an "N pending" badge reflecting the IndexedDB write-queue length
//    (hidden when 0).
//  - Drives the flush triggers: on mount (app load), on the 'online' event,
//    and on a ~30s interval. Toasts when offline entries are synced.
export default function SyncStatus() {
  const toast = useToast()
  const [pending, setPending] = useState(0)
  const [online, setOnline] = useState(
    typeof navigator === 'undefined' ? true : navigator.onLine
  )
  // Avoid overlapping flushes from rapid triggers.
  const flushingRef = useRef(false)

  const flush = useCallback(async () => {
    if (flushingRef.current) return
    flushingRef.current = true
    try {
      const { synced } = await syncOfflineQueue({
        onSynced: (n) => {
          if (n > 0) toast.ok(`Synced ${n} offline ${n === 1 ? 'entry' : 'entries'}.`)
        },
      })
      void synced
    } catch {
      // best-effort; queue stays intact for the next trigger
    } finally {
      flushingRef.current = false
    }
  }, [toast])

  // Keep the badge in sync with the queue (enqueue/remove notify listeners).
  useEffect(() => {
    let alive = true
    queueCount().then((c) => { if (alive) setPending(c) }).catch(() => {})
    const off = onQueueChange((c) => { if (alive) setPending(c) })
    return () => { alive = false; off() }
  }, [])

  // Flush on load + every 30s.
  useEffect(() => {
    flush()
    const id = setInterval(flush, 30000)
    return () => clearInterval(id)
  }, [flush])

  // React to connectivity changes.
  useEffect(() => {
    const goOnline = () => { setOnline(true); flush() }
    const goOffline = () => setOnline(false)
    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    return () => {
      window.removeEventListener('online', goOnline)
      window.removeEventListener('offline', goOffline)
    }
  }, [flush])

  if (online && pending === 0) return null

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {!online && (
        <span
          title="No connection — new entries are saved on this device and will sync automatically."
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '5px 9px', borderRadius: 9,
            background: 'rgba(240,85,109,.14)', color: 'var(--red)',
            fontSize: 11, fontWeight: 700, fontFamily: 'var(--mono)',
            border: '1px solid rgba(240,85,109,.3)', lineHeight: 1,
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--red)' }} />
          Offline
        </span>
      )}
      {pending > 0 && (
        <span
          title={`${pending} entr${pending === 1 ? 'y' : 'ies'} saved on this device, waiting to sync.`}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '5px 9px', borderRadius: 9,
            background: 'rgba(245,166,35,.14)', color: 'var(--amber)',
            fontSize: 11, fontWeight: 700, fontFamily: 'var(--mono)',
            border: '1px solid rgba(245,166,35,.3)', lineHeight: 1,
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--amber)' }} />
          {pending} pending sync
        </span>
      )}
    </div>
  )
}
