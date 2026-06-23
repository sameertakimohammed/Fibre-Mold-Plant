import { enqueue, flushQueue, OFFLINE_QUEUED, makeId } from './offlineQueue'

const TOKEN_KEY = 'fmp_token'

// ---------------------------------------------------------------------------
// API base path. Kept as a single constant so it can be adjusted in one place.
// Everything routed through request() builds URLs from it. The API is versioned
// under /api/v1 (see backend routers). The ONLY unversioned endpoint is the
// infra health probe (/api/health/ready), which is hardcoded in healthReady().
// ---------------------------------------------------------------------------
const API_BASE = '/api/v1'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}
export function setToken(t) {
  if (t) localStorage.setItem(TOKEN_KEY, t)
  else localStorage.removeItem(TOKEN_KEY)
}

// HttpError carries the server status so callers (and the offline flush) can
// distinguish e.g. 409-duplicate from other failures. A network failure (fetch
// throwing — offline, DNS, connection reset) is flagged with isNetworkError so
// it is NEVER confused with a real server response.
class HttpError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'HttpError'
    this.status = status
  }
}
class NetworkError extends Error {
  constructor(cause) {
    super('Network unavailable')
    this.name = 'NetworkError'
    this.isNetworkError = true
    this.cause = cause
  }
}

async function request(path, { method = 'GET', body, form, idempotencyKey } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  // Pass the client UUID through so the server (and any proxy) can dedupe a
  // replayed offline write. Harmless if the backend ignores it.
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey

  let payload
  if (form) {
    payload = new URLSearchParams(form).toString()
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
  } else if (body) {
    payload = JSON.stringify(body)
    headers['Content-Type'] = 'application/json'
  }

  let res
  try {
    res = await fetch(`${API_BASE}${path}`, { method, headers, body: payload })
  } catch (e) {
    // fetch() only throws for network-level failures (offline, DNS, reset),
    // never for HTTP error status codes. This is the ONLY branch that means
    // "we could not reach the server".
    throw new NetworkError(e)
  }

  if (res.status === 401) {
    setToken(null)
    if (!path.includes('/auth/login')) window.location.href = '/login'
  }
  if (!res.ok) {
    let detail = `Error ${res.status}`
    try { detail = (await res.json()).detail || detail } catch {}
    throw new HttpError(detail, res.status)
  }
  if (res.status === 204) return null
  return res.json()
}

// ---------------------------------------------------------------------------
// Offline-capable POST wrapper.
//
// Behavior:
//   1. Try the normal request first (online happy path is unchanged).
//   2. ONLY if it fails with a NetworkError (offline / fetch threw) do we
//      persist the payload to IndexedDB with a client UUID and resolve
//      OPTIMISTICALLY with an OFFLINE_QUEUED marker so the UI can say
//      "saved offline, will sync".
//   3. A server response (4xx/5xx, incl. validation errors) is re-thrown
//      unchanged — it surfaces to the user exactly as today.
//
// `kind` is a label used only for status messages on flush.
async function postOrQueue(kind, path, body) {
  const idempotencyKey = makeId()
  try {
    return await request(path, { method: 'POST', body, idempotencyKey })
  } catch (err) {
    if (err && err.isNetworkError) {
      await enqueue({ kind, path, method: 'POST', body, idempotencyKey })
      return { [OFFLINE_QUEUED]: true, kind }
    }
    throw err // real server error → behave as before
  }
}

// Replays one queued item. Reuses request(); a NetworkError keeps it queued,
// any HttpError (incl. 409 duplicate) is interpreted by flushQueue().
function replayQueued(item) {
  return request(item.path, {
    method: item.method,
    body: item.body,
    idempotencyKey: item.idempotencyKey,
  })
}

// Drain the queue. Exposed so the app shell can trigger it on load / 'online'
// / interval. Returns { synced, failed, remaining }.
export function syncOfflineQueue(opts) {
  return flushQueue(replayQueued, opts)
}

// Re-export the marker + queue subscription so UI code has a single import.
export { OFFLINE_QUEUED } from './offlineQueue'
export { onQueueChange, queueCount } from './offlineQueue'

export const api = {
  login: (username, password) =>
    request('/auth/login', { method: 'POST', form: { username, password } }),
  me: () => request('/auth/me'),
  // Sliding-session renewal: exchange a still-valid token for a fresh one.
  refresh: () => request('/auth/refresh', { method: 'POST' }),
  changePassword: (current_password, new_password) =>
    request('/auth/change-password', { method: 'POST', body: { current_password, new_password } }),

  summary: (start, end) => {
    const q = new URLSearchParams()
    if (start) q.set('start', start)
    if (end) q.set('end', end)
    return request(`/analytics/summary?${q}`)
  },
  periods: () => request('/analytics/periods'),

  // --- AI assistant (Claude). All no-op gracefully when AI is disabled. ---
  aiStatus: () => request('/ai/status'),
  aiAsk: (question) => request('/ai/ask', { method: 'POST', body: { question } }),
  aiCommentary: (start, end) => {
    const q = new URLSearchParams()
    if (start) q.set('start', start)
    if (end) q.set('end', end)
    return request(`/ai/commentary?${q}`)
  },

  // Download a report (auth header + blob → browser save). format is one of
  // 'xlsx' | 'pdf' | 'pptx'; period is the cadence label used in the title and
  // filename ('Daily' | 'Weekly' | 'Monthly'). Defaults keep the dashboard's
  // existing api.downloadReport(start, end) call working unchanged.
  downloadReport: async (start, end, { format = 'xlsx', period = 'Production' } = {}) => {
    const q = new URLSearchParams()
    if (start) q.set('start', start)
    if (end) q.set('end', end)
    if (period) q.set('period', period)
    const token = getToken()
    const res = await fetch(`${API_BASE}/reports/report.${format}?${q}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) throw new Error(`Report failed (${res.status})`)
    const blob = await res.blob()
    const cd = res.headers.get('Content-Disposition') || ''
    const m = cd.match(/filename="?([^"]+)"?/)
    const name = m ? m[1] : `FMP-${period}-${start || 'all'}.${format}`
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = name
    document.body.appendChild(a); a.click(); a.remove()
    URL.revokeObjectURL(url)
  },

  listShifts: (start, end) => {
    const q = new URLSearchParams()
    if (start) q.set('start', start)
    if (end) q.set('end', end)
    return request(`/shifts?${q}`)
  },
  // Offline-capable: queues to IndexedDB on network failure (see postOrQueue).
  createShift: (data) => postOrQueue('shift', '/shifts', data),
  updateShift: (id, data) => request(`/shifts/${id}`, { method: 'PUT', body: data }),
  deleteShift: (id) => request(`/shifts/${id}`, { method: 'DELETE' }),

  listDeliveries: (start, end) => {
    const q = new URLSearchParams()
    if (start) q.set('start', start)
    if (end) q.set('end', end)
    return request(`/deliveries?${q}`)
  },
  createDelivery: (data) => postOrQueue('delivery', '/deliveries', data),
  updateDelivery: (id, data) => request(`/deliveries/${id}`, { method: 'PUT', body: data }),
  deleteDelivery: (id) => request(`/deliveries/${id}`, { method: 'DELETE' }),

  listBales: (start, end) => {
    const q = new URLSearchParams()
    if (start) q.set('start', start)
    if (end) q.set('end', end)
    return request(`/bales?${q}`)
  },
  createBale: (data) => postOrQueue('bale', '/bales', data),
  updateBale: (id, data) => request(`/bales/${id}`, { method: 'PUT', body: data }),
  deleteBale: (id) => request(`/bales/${id}`, { method: 'DELETE' }),

  listFuelDips: (start, end) => {
    const q = new URLSearchParams()
    if (start) q.set('start', start)
    if (end) q.set('end', end)
    return request(`/fuel-dips?${q}`)
  },
  createFuelDip: (data) => postOrQueue('fuel dip', '/fuel-dips', data),
  updateFuelDip: (id, data) => request(`/fuel-dips/${id}`, { method: 'PUT', body: data }),
  deleteFuelDip: (id) => request(`/fuel-dips/${id}`, { method: 'DELETE' }),

  listStock: () => request('/monthly-stock'),
  upsertStock: (period, data) => request(`/monthly-stock/${period}`, { method: 'PUT', body: data }),
  deleteStock: (period) => request(`/monthly-stock/${period}`, { method: 'DELETE' }),

  // KPI targets (manager+ to set). GET is open to any authenticated user.
  listTargets: () => request('/targets'),
  setTarget: (metric, value) => request(`/targets/${metric}`, { method: 'PUT', body: { value } }),
  deleteTarget: (metric) => request(`/targets/${metric}`, { method: 'DELETE' }),

  // Admin: latest database-backup status (age/size/staleness).
  adminBackups: () => request('/admin/backups'),

  listUsers: () => request('/users'),
  createUser: (data) => request('/users', { method: 'POST', body: data }),
  updateUser: (id, data) => request(`/users/${id}`, { method: 'PATCH', body: data }),
  deleteUser: (id) => request(`/users/${id}`, { method: 'DELETE' }),

  // Audit trail (admin). Filters: entity_type, entity_id, action, actor, limit, offset.
  listAudit: (params = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.set(k, v)
    })
    return request(`/audit?${q}`)
  },
  verifyAudit: () => request('/audit/verify'),

  // Health probe used by the degraded-system banner. Resolves to a boolean and
  // never throws — a network failure or non-200 is treated as "not ready".
  healthReady: async () => {
    try {
      const res = await fetch('/api/health/ready')
      return res.ok
    } catch {
      return false
    }
  },

  // Notifications bell. Endpoint may be absent in some builds, so these degrade
  // gracefully: list returns [] on any error (incl. 404), ack swallows errors.
  listNotifications: async (unacknowledgedOnly = true) => {
    try {
      const headers = {}
      const token = getToken()
      if (token) headers['Authorization'] = `Bearer ${token}`
      const q = unacknowledgedOnly ? '?unacknowledged=true' : ''
      const res = await fetch(`${API_BASE}/notifications${q}`, { headers })
      if (!res.ok) return []
      const data = await res.json()
      return Array.isArray(data) ? data : []
    } catch {
      return []
    }
  },
  ackNotification: async (id) => {
    try {
      const headers = {}
      const token = getToken()
      if (token) headers['Authorization'] = `Bearer ${token}`
      await fetch(`${API_BASE}/notifications/${id}/ack`, { method: 'POST', headers })
    } catch {
      // best-effort; caller already removed it from the local list
    }
  },
}
