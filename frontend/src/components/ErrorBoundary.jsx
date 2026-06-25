import { Component } from 'react'
import { isChunkLoadError, reloadOnceForChunk, recentlyReloadedForChunk } from '../lib/chunkReload'

// Catches render-time errors anywhere below it and shows a friendly card
// instead of white-screening the whole dashboard.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // A stale page chunk after a deploy heals itself with a reload — do it once
    // (guarded against loops) rather than stranding the user on the error card.
    if (isChunkLoadError(error) && reloadOnceForChunk()) return
    // Keep a single, quiet console line for diagnosis — no spam.
    console.error('Dashboard render error:', error, info?.componentStack)
  }

  render() {
    if (this.state.error) {
      // Stale-chunk error and a reload is already on the way (see
      // componentDidCatch) — show a calm "updating" card, not the alarm.
      if (isChunkLoadError(this.state.error) && !recentlyReloadedForChunk()) {
        return (
          <div className="main">
            <div className="card" style={{ maxWidth: 520, margin: '8vh auto', textAlign: 'center' }}>
              <div style={{ fontSize: 34, opacity: 0.5, marginBottom: 12 }}>↻</div>
              <h3 style={{ justifyContent: 'center', fontSize: 16, marginBottom: 8 }}>Updating to the latest version…</h3>
              <p style={{ color: 'var(--mut)', fontSize: 13, margin: 0 }}>A new version was just deployed. Refreshing automatically.</p>
            </div>
          </div>
        )
      }
      return (
        <div className="main">
          <div className="card" style={{ maxWidth: 520, margin: '8vh auto', textAlign: 'center' }}>
            <div style={{ fontSize: 34, opacity: 0.5, marginBottom: 12 }}>⚠</div>
            <h3 style={{ justifyContent: 'center', fontSize: 16, marginBottom: 8 }}>
              <span className="dot" />Something went wrong
            </h3>
            <p style={{ color: 'var(--mut)', fontSize: 13, margin: '0 0 18px' }}>
              The dashboard hit an unexpected error. Reloading usually fixes it.
            </p>
            {this.state.error?.message && (
              <div className="banner" style={{ textAlign: 'left', marginBottom: 18 }}>
                {String(this.state.error.message)}
              </div>
            )}
            <button className="btn btn-primary" onClick={() => window.location.reload()}>
              Reload
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
