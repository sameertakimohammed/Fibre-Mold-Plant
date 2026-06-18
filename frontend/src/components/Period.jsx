import { useState, useEffect } from 'react'
import { api } from '../api/client'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const fmtP = (p) => { const [y, m] = p.split('-'); return `${MONTHS[Number(m) - 1]} ${y}` }
const monthRange = (p) => {
  const [y, m] = p.split('-').map(Number)
  const last = new Date(y, m, 0).getDate()
  return { start: `${p}-01`, end: `${p}-${String(last).padStart(2, '0')}` }
}

export function usePeriod() {
  const [periods, setPeriods] = useState([])
  const [mode, setMode] = useState('month')   // 'month' | 'range'
  const [period, setPeriod] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')

  useEffect(() => {
    api.periods().then(r => {
      setPeriods(r.periods)
      if (r.periods.length) {
        setPeriod(r.periods[0])
        const { start, end } = monthRange(r.periods[0])
        setFrom(start); setTo(end)
      }
    })
  }, [])

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
        <select value={period} onChange={e => setPeriod(e.target.value)}>
          {periods.length === 0 && <option>No data</option>}
          {periods.map(p => <option key={p} value={p}>{fmtP(p)}</option>)}
        </select>
      ) : (
        <div className="range-grp">
          <input className="range-in" type="date" value={from} onChange={e => setFrom(e.target.value)} />
          <span className="dash">→</span>
          <input className="range-in" type="date" value={to} onChange={e => setTo(e.target.value)} />
        </div>
      )}
    </div>
  )

  return { periods, period, setPeriod, mode, setMode, from, to, start, end, rangeKey, range, control }
}

// kept for any callers still importing it
export function PeriodPicker({ periods, period, setPeriod }) {
  return (
    <div className="period-pick">
      <select value={period} onChange={e => setPeriod(e.target.value)}>
        {periods.length === 0 && <option>No data</option>}
        {periods.map(p => <option key={p} value={p}>{fmtP(p)}</option>)}
      </select>
    </div>
  )
}
