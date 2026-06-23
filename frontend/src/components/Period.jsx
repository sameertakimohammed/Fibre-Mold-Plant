import { useState } from 'react'

// Current calendar month as YYYY-MM (local time), e.g. "2026-07".
export function currentMonth() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

const monthRange = (p) => {
  const [y, m] = p.split('-').map(Number)
  const last = new Date(y, m, 0).getDate()
  return { start: `${p}-01`, end: `${p}-${String(last).padStart(2, '0')}` }
}

export function usePeriod() {
  // Default to the CURRENT month (computed at mount) rather than the latest
  // month that happens to have data — so opening the app in a new month lands
  // on that month automatically, even before any shift is logged.
  const cur = currentMonth()
  const [mode, setMode] = useState('month')   // 'month' | 'range'
  const [period, setPeriod] = useState(cur)
  const init = monthRange(cur)
  const [from, setFrom] = useState(init.start)
  const [to, setTo] = useState(init.end)

  let start, end
  if (mode === 'range') { start = from || undefined; end = to || undefined }
  else if (period) ({ start, end } = monthRange(period))

  const rangeKey = `${mode}|${start || ''}|${end || ''}`
  // backward-compat helper
  const range = () => ({ start, end })

  const control = (
    <div className="period-pick">
      <div className="seg">
        <button className={mode === 'month' ? 'on' : ''} onClick={() => setMode('month')}>Month</button>
        <button className={mode === 'range' ? 'on' : ''} onClick={() => setMode('range')}>Range</button>
      </div>
      {mode === 'month' ? (
        // Native month/year calendar picker (defaults to the current month).
        <input className="range-in" type="month" value={period} onChange={e => setPeriod(e.target.value)} />
      ) : (
        <div className="range-grp">
          <input className="range-in" type="date" value={from} onChange={e => setFrom(e.target.value)} />
          <span className="dash">→</span>
          <input className="range-in" type="date" value={to} onChange={e => setTo(e.target.value)} />
        </div>
      )}
    </div>
  )

  return { period, setPeriod, mode, setMode, from, to, start, end, rangeKey, range, control }
}

// Month-only calendar picker (used where the Month|Range toggle isn't needed).
export function PeriodPicker({ period, setPeriod }) {
  return (
    <div className="period-pick">
      <input className="range-in" type="month" value={period} onChange={e => setPeriod(e.target.value)} />
    </div>
  )
}
