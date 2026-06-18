import { createContext, useContext, useState, useCallback, useRef } from 'react'

const ToastCtx = createContext(null)
const ICONS = { ok: '✓', err: '✕', info: 'ℹ' }

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const idRef = useRef(0)

  const dismiss = useCallback((id) => {
    setToasts(t => t.filter(x => x.id !== id))
  }, [])

  const push = useCallback((msg, type = 'ok', ttl = 4000) => {
    const id = ++idRef.current
    setToasts(t => [...t, { id, msg, type }])
    if (ttl) setTimeout(() => dismiss(id), ttl)
    return id
  }, [dismiss])

  const toast = {
    ok: (m, ttl) => push(m, 'ok', ttl),
    err: (m, ttl) => push(m, 'err', ttl ?? 6000),
    info: (m, ttl) => push(m, 'info', ttl),
  }

  return (
    <ToastCtx.Provider value={toast}>
      {children}
      <div className="toasts">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.type}`}>
            <span className="t-ic">{ICONS[t.type]}</span>
            <span className="t-msg">{t.msg}</span>
            <button className="t-x" onClick={() => dismiss(t.id)}>×</button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export const useToast = () => useContext(ToastCtx)
