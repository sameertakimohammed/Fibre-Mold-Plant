// Recovery for stale lazy-loaded chunks after a deploy.
//
// Each page is a React.lazy() chunk with a content-hash filename
// (e.g. Production-DC2faVV7.js). A new deploy renames every chunk and removes
// the old files, so a tab still running the previous build 404s the moment it
// lazy-loads a page it hasn't visited yet — surfacing as
// "Failed to fetch dynamically imported module". The cure is simply to reload:
// a fresh index.html references the new filenames.
//
// This module centralises that detection + a one-reload-per-burst guard so a
// genuinely-unreachable chunk can't trigger an infinite reload loop.
const KEY = 'fmp_chunk_reload_at'
const WINDOW_MS = 10000

export function isChunkLoadError(error) {
  if (!error) return false
  if (error.name === 'ChunkLoadError') return true
  const msg = String(error.message || error)
  return /dynamically imported module|module script failed|failed to fetch dynamically|error loading dynamically|unable to preload/i.test(msg)
}

function lastReloadAt() {
  try { return Number(sessionStorage.getItem(KEY) || 0) } catch { return 0 }
}

// True if we auto-reloaded for a chunk error within the guard window — used by
// the ErrorBoundary to decide whether a reload is already on the way.
export function recentlyReloadedForChunk() {
  return Date.now() - lastReloadAt() <= WINDOW_MS
}

// Reload once to pick up the new build. Returns true if it triggered a reload,
// false if the guard suppressed it (so the caller can show the manual fallback).
export function reloadOnceForChunk() {
  if (recentlyReloadedForChunk()) return false
  try { sessionStorage.setItem(KEY, String(Date.now())) } catch { /* private mode */ }
  window.location.reload()
  return true
}
