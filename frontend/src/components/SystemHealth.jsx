import { useState, useEffect } from 'react'
import { api } from '../api/client'

// Polls /api/health/ready every ~30s. When the backend reports unhealthy
// (non-200) it renders a dismissible banner so operators know data may not save.
export default function SystemHealth() {
  const [degraded, setDegraded] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    let alive = true
    const check = async () => {
      const ok = await api.healthReady()
      if (!alive) return
      setDegraded(!ok)
      if (ok) setDismissed(false) // re-arm the banner once healthy again
    }
    check()
    const id = setInterval(check, 30000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  if (!degraded || dismissed) return null

  return (
    <div
      className="banner"
      style={{
        margin: '0 0 0',
        borderRadius: 0,
        borderLeft: 0, borderRight: 0, borderTop: 0,
        background: 'rgba(240,85,109,.12)',
        borderColor: 'rgba(240,85,109,.3)',
        color: 'var(--red)',
        display: 'flex', alignItems: 'center', gap: 12,
      }}
    >
      <span style={{ flex: 1 }}>
        ⚠ System degraded — the database may be unreachable. Data may not save.
      </span>
      <button
        className="btn btn-ghost btn-sm"
        onClick={() => setDismissed(true)}
        aria-label="Dismiss"
      >
        Dismiss
      </button>
    </div>
  )
}
