import { useState, useEffect, useMemo } from 'react'
import { api } from '../api/client'
import { Kpi, Card, PageHead, Empty } from '../components/ui'
import { useToast } from '../context/ToastContext'
import { C, fmt, fmt1 } from '../api/charts'
import { buildTarget, cap } from '../lib/targets'
import AskAI from '../components/AskAI'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const fmtMonth = (p) => { const [y, m] = p.split('-'); return `${MONTHS[Number(m) - 1]} ${y}` }
const pad = (n) => String(n).padStart(2, '0')
const isoLocal = (dt) => `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`
const lastDayOf = (period) => { const [y, m] = period.split('-').map(Number); return `${period}-${pad(new Date(y, m, 0).getDate())}` }

const monthRange = (p) => { const [y, m] = p.split('-').map(Number); return { start: `${p}-01`, end: `${p}-${pad(new Date(y, m, 0).getDate())}` } }
const curMonth = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}` }
const monthsAgo = (n) => { const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - n); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}` }
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
  const [cadence, setCadence] = useState('monthly')
  // Default the pickers to the CURRENT period (today / this month) so a new
  // month opens on itself; the calendar controls let you pick any past period.
  const [day, setDay] = useState(isoLocal(new Date()))
  const [weekRef, setWeekRef] = useState(isoLocal(new Date()))
  const [month, setMonth] = useState(curMonth())
  // Multi-month PowerPoint deck range (independent of the single-period pickers).
  const [pptFrom, setPptFrom] = useState(monthsAgo(2))
  const [pptTo, setPptTo] = useState(curMonth())
  const [summary, setSummary] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState('')
  const [aiOn, setAiOn] = useState(false)
  const [commentary, setCommentary] = useState('')

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

  // Multi-month deck range: normalise From/To (YYYY-MM strings sort correctly).
  const deck = useMemo(() => {
    if (!pptFrom || !pptTo) return null
    const lo = pptFrom <= pptTo ? pptFrom : pptTo
    const hi = pptFrom <= pptTo ? pptTo : pptFrom
    const months = (Number(hi.slice(0, 4)) - Number(lo.slice(0, 4))) * 12
      + (Number(hi.slice(5)) - Number(lo.slice(5))) + 1
    return { start: `${lo}-01`, end: lastDayOf(hi), months }
  }, [pptFrom, pptTo])
  const deckSpan = deck ? `${fmtMonth(deck.start.slice(0, 7))} → ${fmtMonth(deck.end.slice(0, 7))}` : '—'
  const deckMonths = deck ? deck.months : 0

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

  // The multi-month PowerPoint deck (per-month detail + trend slides).
  const downloadDeck = async () => {
    if (!deck) return
    setBusy('pptx')
    try {
      await api.downloadReport(deck.start, deck.end, { format: 'pptx', period: 'Monthly' })
      toast.ok(`PowerPoint deck downloaded (${deckMonths} month${deckMonths > 1 ? 's' : ''}).`)
    } catch (e) {
      toast.err(e.message || 'Report failed')
    } finally { setBusy('') }
  }

  const k = summary?.kpis
  const tg = summary?.targets || {}
  const tp = summary?.target_period   // matches the chosen cadence (daily/weekly/monthly)
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
              <input className="range-in" type="month" value={month} onChange={e => setMonth(e.target.value)} />
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
        </div>

        {cadence === 'monthly' && (
          <div style={{ marginTop: 10, borderTop: '1px solid var(--line)', paddingTop: 12 }}>
            <div className="rep-actions" style={{ alignItems: 'center' }}>
              <span className="rep-hint" style={{ marginRight: 'auto' }}>
                <strong>PowerPoint deck</strong> — per-month detail + overall trend slides across a range
              </span>
              <span className="rep-hint">From</span>
              <input className="range-in" type="month" value={pptFrom} onChange={e => setPptFrom(e.target.value)} />
              <span className="rep-hint">to</span>
              <input className="range-in" type="month" value={pptTo} onChange={e => setPptTo(e.target.value)} />
              <button className="btn btn-primary btn-sm" disabled={!pptFrom || !pptTo || busy} onClick={downloadDeck}>
                {busy === 'pptx' ? 'Preparing…' : '⤓ PowerPoint'}
              </button>
            </div>
            <div className="rep-span" style={{ marginTop: 8 }}>
              Deck period: <strong>{deckSpan}</strong>
              {deckMonths > 1 && <span className="rep-hint"> · {deckMonths} months (adds trend-comparison slides)</span>}
            </div>
          </div>
        )}

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
            <div className="rep-preview-h">Preview · {spanText}{tp ? ` · vs ${cap(tp)} target` : ''}</div>
            <div className="kpis">
              <Kpi label="Total Trays" value={fmt(k.total_qty)} note={`${k.active_days} active days`} accent={C.amber} />
              <Kpi label="30's Trays" value={fmt(k.prod_30)} note="formed" accent={C.green}
                target={buildTarget(k.prod_30, tg.prod_30, false, '', tp)} />
              <Kpi label="12's Cartons" value={fmt(k.prod_12)} note="formed" accent={C.teal}
                target={buildTarget(k.prod_12, tg.prod_12, false, '', tp)} />
              <Kpi label="Fuel Burned" value={fmt(k.total_fuel)} unit="L"
                note={`${fmt1(k.fuel_eff)} L/1k${tg.fuel_eff ? ` · target ${fmt1(tg.fuel_eff)}` : ''}`} accent={C.blue}
                target={buildTarget(k.total_fuel, tg.diesel, true, ' L', tp)} />
              <Kpi label="Downtime" value={fmt1(k.total_downtime_min / 60)} unit="hrs" note={`${fmt1(k.downtime_pct)}% of scheduled`} accent={C.red}
                target={buildTarget(k.downtime_pct, tg.downtime_pct, true, '%', tp)} />
              <Kpi label="Re-pulped" value={fmt(k.total_repulped)} note={`${fmt1(k.repulp_rate)}% reject rate`} accent={C.purple}
                target={buildTarget(k.repulp_rate, tg.repulp_rate, true, '%', tp)} />
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
