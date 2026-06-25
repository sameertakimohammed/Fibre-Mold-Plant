// Recovery for stale lazy-loaded chunks after a deploy.
//
// Each page is a React.lazy() chunk with a content-hash filename
// (e.g. Production-DC2faVV7.js). A new deploy renames every chunk and removes
// the old files, so a tab still running the previous build 404s the moment it
// lazy-loads a page it hasn't visited yet — surfacing as
// "Failed to fetch dynamically imported module". The cure is to reload: a fresh
// index.html references the new filenames.
//
// Guard: at most MAX_RELOADS automatic reloads within WINDOW_MS. A genuinely
// broken/unreachable chunk therefore lands on the manual error card after a
// couple of attempts instead of reload-looping forever. The burst record is
// time-boxed, so a much-later unrelated chunk error starts fresh on its own.
const KEY = 'fmp_chunk_reload'
const WINDOW_MS = 30000
const MAX_RELOADS = 2

// Per-page-load latch: a single failed navigation can fire BOTH the
// vite:preloadError event (main.jsx) and the React.lazy rejection
// (ErrorBoundary). Only count + act on the first call this load.
let scheduledThisLoad = false

function readBurst() {
  try {
    const r = JSON.parse(sessionStorage.getItem(KEY) || 'null')
    if (r && Date.now() - r.at <= WINDOW_MS) return r
  } catch { /* private mode / bad JSON */ }
  return null   // none, or window expired → treat as a fresh burst
}

export function isChunkLoadError(error) {
  if (!error) return false
  if (error.name === 'ChunkLoadError') return true
  const msg = String(error.message || error)
  return /dynamically imported module|module script failed|failed to fetch dynamically|error loading dynamically|unable to preload/i.test(msg)
}

// True once the automatic reloads in the current burst are exhausted — the
// ErrorBoundary uses this to choose the alarm card over the "Updating…" card.
export function hasGivenUpOnChunk() {
  const r = readBurst()
  return !!r && r.count >= MAX_RELOADS
}

// Reload once to pick up the new build. Returns true if a reload was triggered
// (or is already pending this load), false once the attempt cap is hit so the
// caller can fall back to the manual error card.
export function reloadOnceForChunk() {
  if (scheduledThisLoad) return true
  const count = readBurst()?.count || 0
  if (count >= MAX_RELOADS) return false
  try { sessionStorage.setItem(KEY, JSON.stringify({ count: count + 1, at: Date.now() })) } catch { /* private mode */ }
  scheduledThisLoad = true
  window.location.reload()
  return true
}
