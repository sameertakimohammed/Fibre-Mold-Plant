import { useEffect } from 'react'

const fmtPct = n => (Math.round(Math.abs(n) * 10) / 10).toLocaleString()

// delta = { value, suffix?: '%'|'pp', betterWhenLower?: bool }
function Delta({ delta }) {
  if (!delta || delta.value == null || !isFinite(delta.value)) return null
  const v = delta.value
  const suffix = delta.suffix ?? '%'
  const up = v > 0.05
  const down = v < -0.05
  const good = delta.betterWhenLower ? down : up
  const bad = delta.betterWhenLower ? up : down
  const cls = good ? 'up' : bad ? 'down' : 'flat'
  const arrow = up ? '▲' : down ? '▼' : '–'
  return <span className={`k-delta ${cls}`}>{arrow} {fmtPct(v)}{suffix}</span>
}

export function Spark({ data = [], color = '#f5a623', height = 30 }) {
  const pts = data.filter(n => isFinite(n))
  if (pts.length < 2) return null
  const w = 100, h = height
  const max = Math.max(...pts), min = Math.min(...pts)
  const span = max - min || 1
  const step = w / (pts.length - 1)
  const coords = pts.map((v, i) => [i * step, h - ((v - min) / span) * (h - 4) - 2])
  const line = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const area = `0,${h} ${line} ${w},${h}`
  const id = 'sg' + color.replace('#', '')
  return (
    <svg className="k-spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" width="100%" height={height}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline points={area} fill={`url(#${id})`} stroke="none" />
      <polyline points={line} fill="none" stroke={color} strokeWidth="1.6"
        strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

export function Kpi({ label, value, unit, note, accent, delta, spark, sparkColor }) {
  return (
    <div className="kpi" style={{ '--accent': accent }}>
      <div className="k-top">
        <div className="k-lbl">{label}</div>
        <Delta delta={delta} />
      </div>
      <div className="k-val">{value}{unit && <span className="k-unit">{unit}</span>}</div>
      {note && <div className="k-note">{note}</div>}
      {spark && spark.length > 1 && <Spark data={spark} color={sparkColor || accent} />}
    </div>
  )
}

export function Card({ title, sub, children, span2, right }) {
  return (
    <div className={`card ${span2 ? 'span2' : ''}`}>
      {(title || right) && (
        <div className="entry-head" style={{ marginBottom: sub ? 0 : 14 }}>
          <h3><span className="dot" />{title}</h3>
          {right}
        </div>
      )}
      {sub && <div className="csub">{sub}</div>}
      {children}
    </div>
  )
}

export function PageHead({ title, sub, right }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <div className="ph-sub">{sub}</div>}
      </div>
      {right && <div className="head-actions">{right}</div>}
    </div>
  )
}

export function Empty({ icon = '∅', title = 'Nothing here yet', detail }) {
  return (
    <div className="empty">
      <div className="e-ic">{icon}</div>
      <div className="e-t">{title}</div>
      {detail && <div className="e-d">{detail}</div>}
    </div>
  )
}

// Dashboard-style loading skeleton
export function PageSkeleton({ kpis = 5, cards = 3 }) {
  return (
    <div className="main">
      <div className="page-head"><div><div className="skel" style={{ width: 200, height: 24 }} />
        <div className="skel" style={{ width: 140, height: 12, marginTop: 8 }} /></div></div>
      <div className="skel-kpis">
        {Array.from({ length: kpis }).map((_, i) => <div key={i} className="skel skel-kpi" />)}
      </div>
      <div className="grid g2">
        {Array.from({ length: cards }).map((_, i) => <div key={i} className={`skel skel-card ${i === 0 ? 'span2' : ''}`} />)}
      </div>
    </div>
  )
}

export function Modal({ title, sub, onClose, children, footer, maxWidth }) {
  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => { window.removeEventListener('keydown', onKey); document.body.style.overflow = '' }
  }, [onClose])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={maxWidth ? { maxWidth } : undefined} onClick={e => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <h3>{title}</h3>
            {sub && <div className="m-sub">{sub}</div>}
          </div>
          <button className="modal-x" onClick={onClose} aria-label="Close">×</button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  )
}
