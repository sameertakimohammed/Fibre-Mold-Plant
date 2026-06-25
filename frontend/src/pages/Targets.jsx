import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { PageHead, Card } from '../components/ui'
import { fmt, fmt1 } from '../api/charts'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { TARGET_METRICS, PERIODS, cap, buildTarget, actualForMetric } from '../lib/targets'

const pad = (n) => String(n).padStart(2, '0')
// Current calendar month [start, end] (local), for the "this month" attainment.
const thisMonthRange = () => {
  const d = new Date()
  const y = d.getFullYear(), m = d.getMonth() + 1
  return { start: `${y}-${pad(m)}-01`, end: `${y}-${pad(m)}-${pad(new Date(y, m, 0).getDate())}` }
}

// Management KPI goals at daily / weekly / monthly cadence. Everyone can view;
// manager+ can edit. The grid also shows this month's actual vs the monthly goal
// so a manager can set-and-check without leaving the page.
export default function Targets() {
  const { can } = useAuth()
  const toast = useToast()
  const editable = can('manager')
  const [vals, setVals] = useState(null)   // { metric: { period: 'string' } }
  const [orig, setOrig] = useState(null)
  const [actuals, setActuals] = useState(null)   // current-month kpis (best-effort)
  const [mtargets, setMtargets] = useState({})   // current-month resolved targets
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const load = () => {
    setErr('')
    const { start, end } = thisMonthRange()
    Promise.all([
      api.listTargets(),
      api.summary(start, end).catch(() => null),   // attainment is best-effort
    ]).then(([rows, summary]) => {
      const o = {}
      TARGET_METRICS.forEach(m => { o[m.key] = {}; PERIODS.forEach(p => { o[m.key][p] = '' }) })
      rows.forEach(r => { if (o[r.metric] && PERIODS.includes(r.period)) o[r.metric][r.period] = String(r.value) })
      setVals(o); setOrig(JSON.parse(JSON.stringify(o)))
      setActuals(summary?.kpis || null)
      setMtargets(summary?.targets || {})
    }).catch(e => setErr(e.message))
  }
  useEffect(load, [])

  const set = (m, p, v) => setVals(s => ({ ...s, [m]: { ...s[m], [p]: v } }))
  const dirty = vals && orig && JSON.stringify(vals) !== JSON.stringify(orig)

  const save = async () => {
    setBusy(true)
    const skipped = []
    try {
      for (const m of TARGET_METRICS) {
        for (const p of PERIODS) {
          const raw = vals[m.key][p]
          if (raw === orig[m.key][p]) continue           // unchanged cell
          const num = parseFloat(raw)
          // Blank — or 0, which renders no marker — clears the target.
          if (raw === '' || raw == null || num === 0) { await api.deleteTarget(p, m.key); continue }
          if (!isFinite(num) || num < 0) { skipped.push(`${m.label} (${p})`); continue }
          await api.setTarget(p, m.key, num)
        }
      }
      if (skipped.length) toast.err(`Saved. Skipped ${skipped.length} invalid cell(s) — must be 0 or greater: ${skipped.join(', ')}`)
      else toast.ok('Targets saved.')
      load()
    } catch (e) { toast.err(e.message) } finally { setBusy(false) }
  }

  const fmtVal = (m, v) => (v == null ? '—' : (m.kind === 'volume' ? fmt(v) : fmt1(v)))

  return (
    <div className="main">
      <PageHead title="Targets" sub="Daily, weekly & monthly KPI goals — with this month's progress against the monthly goal" />
      {err && <div className="err">{err}</div>}
      <Card title="KPI Targets"
        sub={editable ? 'Set a goal for each metric at each cadence' : 'Management goals (manager+ can edit)'}>
        {!vals ? <div className="hint">Loading…</div> : (
          <>
            <div className="tgt-wrap">
              <table className="tgt-grid">
                <thead>
                  <tr>
                    <th>Metric</th>
                    {PERIODS.map(p => <th key={p}>{cap(p)}</th>)}
                    <th className="tgt-actual-h">This month</th>
                  </tr>
                </thead>
                <tbody>
                  {TARGET_METRICS.map(m => {
                    const actual = actualForMetric(m.key, actuals)
                    const att = buildTarget(actual, mtargets[m.key], m.lower, '', 'monthly')
                    return (
                      <tr key={m.key}>
                        <td className="tgt-metric">
                          {m.label}
                          <span className="hint"> {m.unit.trim() || (m.kind === 'volume' ? 'pcs' : '')}{m.lower ? ' · lower better' : ''}</span>
                        </td>
                        {PERIODS.map(p => (
                          <td key={p}>
                            <input type="number" min="0" value={vals[m.key][p]} placeholder="—"
                              disabled={!editable || busy}
                              onChange={e => set(m.key, p, e.target.value)} />
                          </td>
                        ))}
                        <td className="tgt-actual">
                          {actuals ? (
                            <>
                              <span className="tgt-act-val">{fmtVal(m, actual)}</span>
                              {att && <span className={`tgt-att ${att.met ? 'met' : 'miss'}`}>{Math.round(att.pct)}%</span>}
                            </>
                          ) : '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="hint" style={{ marginTop: 12 }}>
              Daily = a normal weekday · Weekly = Mon–Fri (5 days) · Saturday = the reduced Saturday run · Monthly = the planned month.
              Volume targets (trays, litres) are per-period totals; rates (L/1k, %) are the same goal at every cadence.
              “This month” compares the month-to-date actual against the monthly goal.
              {editable ? ' Blank a cell (or enter 0) to remove that target.' : ''}
            </div>
            {editable && (
              <div className="form-actions">
                <button className="btn btn-primary" disabled={busy || !dirty} onClick={save}>
                  {busy ? 'Saving…' : 'Save Targets'}
                </button>
                {dirty && <button className="btn btn-ghost" disabled={busy} onClick={load}>Reset</button>}
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  )
}
