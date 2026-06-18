import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '../api/client'

const SEV = {
  critical: { cls: 'err', ic: '✕', color: 'var(--red)' },
  warn: { cls: 'info', ic: '!', color: 'var(--amber)' },
  info: { cls: 'info', ic: 'ℹ', color: 'var(--blue)' },
}

function fmtTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  if (isNaN(d)) return ''
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return d.toLocaleDateString()
}

// Polls /api/notifications?unacknowledged=true every ~60s. If the endpoint is
// absent (404) or unreachable, api.listNotifications returns [] — so this just
// shows zero, no errors, no broken UI.
export default function NotificationsBell() {
  const [items, setItems] = useState([])
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)

  const refresh = useCallback(async () => {
    const data = await api.listNotifications(true)
    setItems(data)
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 60000)
    return () => clearInterval(id)
  }, [refresh])

  // Close the dropdown on outside click.
  useEffect(() => {
    if (!open) return
    const onDoc = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  const ack = async (id) => {
    setItems(list => list.filter(n => n.id !== id)) // optimistic
    await api.ackNotification(id)
  }

  const count = items.length

  return (
    <div className="notif" ref={wrapRef} style={{ position: 'relative' }}>
      <button
        className="bell-btn"
        onClick={() => setOpen(o => !o)}
        aria-label="Notifications"
        style={{ position: 'relative' }}
      >
        🔔
        {count > 0 && (
          <span style={{
            position: 'absolute', top: -4, right: -4, minWidth: 18, height: 18,
            padding: '0 5px', borderRadius: 9, background: 'var(--red)', color: '#fff',
            fontSize: 10, fontWeight: 700, fontFamily: 'var(--mono)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1,
          }}>
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 8px)', right: 0, width: 340, maxWidth: '90vw',
          background: 'var(--panel)', border: '1px solid var(--line2)', borderRadius: 'var(--r)',
          boxShadow: 'var(--sh-lg)', zIndex: 60, overflow: 'hidden',
        }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '12px 14px', borderBottom: '1px solid var(--line)',
          }}>
            <strong style={{ fontSize: 13 }}>Notifications</strong>
            <span className="csub" style={{ margin: 0 }}>{count} unread</span>
          </div>
          <div style={{ maxHeight: 360, overflowY: 'auto' }}>
            {count === 0 && (
              <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--dim)', fontFamily: 'var(--mono)', fontSize: 12 }}>
                Nothing new.
              </div>
            )}
            {items.map(n => {
              const s = SEV[n.severity] || SEV.info
              return (
                <div key={n.id} style={{
                  display: 'flex', gap: 10, alignItems: 'flex-start',
                  padding: '12px 14px', borderBottom: '1px solid var(--line)',
                  borderLeft: `3px solid ${s.color}`,
                }}>
                  <span style={{ color: s.color, fontSize: 14, lineHeight: 1.3 }}>{s.ic}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, lineHeight: 1.35 }}>{n.message}</div>
                    <div className="csub" style={{ margin: '4px 0 0' }}>{fmtTime(n.created_at)}</div>
                  </div>
                  <button className="btn btn-ghost btn-sm" onClick={() => ack(n.id)}>Ack</button>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
