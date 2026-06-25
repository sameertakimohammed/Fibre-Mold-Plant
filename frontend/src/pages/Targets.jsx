import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { PageHead, Card } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { TARGET_METRICS, PERIODS, cap } from '../lib/targets'

// Management KPI goals at daily / weekly / monthly cadence. Everyone can view;
// manager+ can edit. The dashboard and reports compare actuals against the
// target for the cadence being viewed.
export default function Targets() {
  const { can } = useAuth()
  const toast = useToast()
  const editable = can('manager')
  const [vals, setVals] = useState(null)   // { metric: { period: 'string' } }
  const [orig, setOrig] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const load = () => {
    setErr('')
    api.listTargets().then(rows => {
      const o = {}
      TARGET_METRICS.forEach(m => { o[m.key] = {}; PERIODS.forEach(p => { o[m.key][p] = '' }) })
      rows.forEach(r => { if (o[r.metric] && PERIODS.includes(r.period)) o[r.metric][r.period] = String(r.value) })
      setVals(o); setOrig(JSON.parse(JSON.stringify(o)))
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
          if (raw === '' || raw == null) { await api.deleteTarget(p, m.key); continue }
          const num = parseFloat(raw)
          if (!isFinite(num) || num < 0) { skipped.push(`${m.label} (${p})`); continue }
          await api.setTarget(p, m.key, num)
        }
      }
      if (skipped.length) toast.err(`Saved. Skipped ${skipped.length} invalid cell(s) — must be 0 or greater: ${skipped.join(', ')}`)
      else toast.ok('Targets saved.')
      load()
    } catch (e) { toast.err(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="main">
      <PageHead title="Targets" sub="Daily, weekly & monthly KPI goals — compared against actuals on the dashboard & reports" />
      {err && <div className="err">{err}</div>}
      <Card title="KPI Targets"
        sub={editable ? 'Set a goal for each metric at each cadence' : 'Management goals (manager+ can edit)'}>
        {!vals ? <div className="hint">Loading…</div> : (
          <>
            <div className="tgt-wrap">
              <table className="tgt-grid">
                <thead>
                  <tr><th>Metric</th>{PERIODS.map(p => <th key={p}>{cap(p)}</th>)}</tr>
                </thead>
                <tbody>
                  {TARGET_METRICS.map(m => (
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
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="hint" style={{ marginTop: 12 }}>
              Volume targets (trays, litres) are per-period totals; rates (L/1k, %) are the same goal at every cadence.
              {editable ? ' Blank a cell to remove that target.' : ''}
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
