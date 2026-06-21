import { useState, useEffect, useMemo } from 'react'
import { api } from '../api/client'
import { Kpi, Card, PageHead, Empty } from '../components/ui'
import { useToast } from '../context/ToastContext'
import { C, fmt, fmt1 } from '../api/charts'
import AskAI from '../components/AskAI'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const fmtMonth = (p) => { const [y, m] = p.split('-'); return `${MONTHS[Number(m) - 1]} ${y}` }
const pad = (n) => String(n).padStart(2, '0')
const isoLocal = (dt) => `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`
const lastDayOf = (period) => { const [y, m] = period.split('-').map(Number); return `${period}-${pad(new Date(y, m, 0).getDate())}` }

const monthRange = (p) => { const [y, m] = p.split('-').map(Number); return { start: `${p}-01`, end: `${p}-${pad(new Date(y, m, 0).getDate())}` } }
const dayRange = (d) => ({ start: d, end: d })
const weekRange = (d) => {
  const [y, m, day] = d.split('-').map(Number)
  const dow = (new Date(y, m - 1, day).getDay() + 6) % 7 // 0 = Monday
  return { start: isoLocal(new Date(y, m - 1, day - dow)), end: isoLocal(new Date(y, m - 1, day - dow + 6)) }
}

const CADENCES = [
  { key: 'daily', label: 'Daily', period: 'Daily' },
  { key: 'weekly', label: 'Weekly', period: 'Weekly' },
  { key: 'monthly', label: 'Monthly', period: 'Monthly' },
]

export default function Reports() {
  const toast = useToast()
  const [periods, setPeriods] = useState([])
  const [cadence, setCadence] = useState('monthly')
  const [day, setDay] = useState('')
  const [weekRef, setWeekRef] = useState('')
  const [month, setMonth] = useState('')
  const [summary, setSummary] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState('')
  const [aiOn, setAiOn] = useState(false)
  const [commentary, setCommentary] = useState('')

  // Seed the pickers off the latest month that actually has data, so the first
  // view shows real numbers (today may be in an empty month).
  useEffect(() => {
    api.periods().then(r => {
      setPeriods(r.periods || [])
      if (r.periods?.length) {
        const latest = r.periods[0]
        setMonth(latest)
        setDay(lastDayOf(latest))
        setWeekRef(lastDayOf(latest))
      } else {
        const today = isoLocal(new Date())
        setDay(today); setWeekRef(today)
      }
    }).catch(e => setErr(e.message))
  }, [])

  // Is the AI assistant configured? Drives the AI section's visibility.
  useEffect(() => { api.aiStatus().then(r => setAiOn(!!r.enabled)).catch(() => setAiOn(false)) }, [])

  const active = CADENCES.find(c => c.key === cadence)
  const range = useMemo(() => {
    if (cadence === 'daily') return day ? dayRange(day) : null
    if (cadence === 'weekly') return weekRef ? weekRange(weekRef) : null
    return month ? monthRange(month) : null
  }, [cadence, day, weekRef, month])

  const spanText = useMemo(() => {
    if (!range) return ''
    if (range.start === range.end) return range.start
    return `${range.start} → ${range.end}`
  }, [range])

  // Live preview of the figures the report will contain.
  useEffect(() => {
    if (!range) return
    setSummary(null); setErr(''); setCommentary('')
    api.summary(range.start, range.end).then(setSummary).catch(e => setErr(e.message))
  }, [range?.start, range?.end])

  const generateCommentary = async () => {
    if (!range) return
    setBusy('commentary'); setCommentary('')
    try {
      const r = await api.aiCommentary(range.start, range.end)
      setCommentary(r.commentary || 'No commentary was generated for this period.')
    } catch (e) {
      toast.err(e.message || 'Commentary failed')
    } finally { setBusy('') }
  }

  const download = async (format, period = active.period) => {
    if (!range) return
    const busyKey = period === 'MonthEnd' ? `me-${format}` : format
    setBusy(busyKey)
    try {
      await api.downloadReport(range.start, range.end, { format, period })
      toast.ok(`${period === 'MonthEnd' ? 'Month End ' : ''}${format.toUpperCase()} report downloaded.`)
    } catch (e) {
      toast.err(e.message || 'Report failed')
    } finally { setBusy('') }
  }

  const k = summary?.kpis
  const hasData = k && k.total_qty > 0

  return (
    <div className="main">
      <PageHead title="Reports" sub="Generate daily, weekly & monthly production reports" />

      <Card title="Build a report" sub="Choose a period, preview the figures, then download">
        <div className="rep-controls">
          <div className="seg">
            {CADENCES.map(c => (
              <button key={c.key} className={cadence === c.key ? 'on' : ''} onClick={() => setCadence(c.key)}>
                {c.label}
              </button>
            ))}
          </div>

          <div className="period-pick">
            {cadence === 'daily' && (
              <input className="range-in" type="date" value={day} onChange={e => setDay(e.target.value)} />
            )}
            {cadence === 'weekly' && (
              <>
                <input className="range-in" type="date" value={weekRef} onChange={e => setWeekRef(e.target.value)} />
                <span className="rep-hint">week of the chosen day (Mon–Sun)</span>
              </>
            )}
            {cadence === 'monthly' && (
              <select value={month} onChange={e => setMonth(e.target.value)}>
                {periods.length === 0 && <option>No data</option>}
                {periods.map(p => <option key={p} value={p}>{fmtMonth(p)}</option>)}
              </select>
            )}
          </div>
        </div>

        <div className="rep-span">Reporting period: <strong>{spanText || '—'}</strong></div>

        <div className="rep-actions">
          <button className="btn btn-primary btn-sm" disabled={!range || busy} onClick={() => download('xlsx')}>
            {busy === 'xlsx' ? 'Preparing…' : '⤓ Excel'}
          </button>
          <button className="btn btn-ghost btn-sm" disabled={!range || busy} onClick={() => download('pdf')}>
            {busy === 'pdf' ? 'Preparing…' : '⤓ PDF'}
          </button>
          <button className="btn btn-ghost btn-sm" disabled={!range || busy} onClick={() => download('csv')}>
            {busy === 'csv' ? 'Preparing…' : '⤓ CSV'}
          </button>
          {cadence === 'monthly' && (
            <button className="btn btn-ghost btn-sm" disabled={!range || busy} onClick={() => download('pptx')}>
              {busy === 'pptx' ? 'Preparing…' : '⤓ PowerPoint'}
            </button>
          )}
          {cadence === 'monthly' && <span className="rep-hint">PowerPoint is a management summary deck</span>}
        </div>

        {cadence === 'monthly' && (
          <div className="rep-actions" style={{ marginTop: 10, borderTop: '1px solid var(--line)', paddingTop: 12 }}>
            <span className="rep-hint" style={{ marginRight: 'auto' }}>
              <strong>Month End Report</strong> — the plant's stock &amp; materials summary (diesel, goods produced, balance stock, labels, pallets, bales)
            </span>
            <button className="btn btn-primary btn-sm" disabled={!range || busy} onClick={() => download('xlsx', 'MonthEnd')}>
              {busy === 'me-xlsx' ? 'Preparing…' : '⤓ Month End Excel'}
            </button>
            <button className="btn btn-ghost btn-sm" disabled={!range || busy} onClick={() => download('pdf', 'MonthEnd')}>
              {busy === 'me-pdf' ? 'Preparing…' : '⤓ Month End PDF'}
            </button>
          </div>
        )}
      </Card>

      {err && <div className="err">{err}</div>}

      {summary && (
        hasData ? (
          <>
            <div className="rep-preview-h">Preview · {spanText}</div>
            <div className="kpis">
              <Kpi label="Total Trays" value={fmt(k.total_qty)} note={`${k.active_days} active days`} accent={C.amber} />
              <Kpi label="Avg / Day" value={fmt(k.avg_per_day)} note="trays produced" accent={C.green} />
              <Kpi label="Fuel Burned" value={fmt(k.total_fuel)} unit="L" note={`${fmt1(k.fuel_eff)} L / 1k trays`} accent={C.blue} />
              <Kpi label="Downtime" value={fmt1(k.total_downtime_min / 60)} unit="hrs" note={`${fmt1(k.downtime_pct)}% of scheduled`} accent={C.red} />
              <Kpi label="Re-pulped" value={fmt(k.total_repulped)} note={`${fmt1(k.repulp_rate)}% reject rate`} accent={C.purple} />
            </div>
          </>
        ) : (
          <Empty icon="▤" title="No data in this period" detail="Pick another date or month — the report would come out empty." />
        )
      )}

      {aiOn && (
        <>
          <Card title="Plant Manager's Commentary" sub={`AI analysis of ${spanText || 'the selected period'} (also embedded in the Month End Report)`}>
            <button className="btn btn-primary btn-sm" disabled={!range || busy} onClick={generateCommentary}>
              {busy === 'commentary' ? 'Generating…' : (commentary ? '↻ Regenerate' : '✦ Generate commentary')}
            </button>
            {commentary && <div className="ai-output">{commentary}</div>}
          </Card>
          <AskAI />
        </>
      )}
    </div>
  )
}
