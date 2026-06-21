import { useState, useEffect, useCallback } from 'react'
import { Bar, Line } from 'react-chartjs-2'
import { api } from '../api/client'
import { C, PROD_COLORS, gridX, gridY, fmt, fmt1, dlabel } from '../api/charts'
import { Kpi, Card, PageHead, PageSkeleton, Empty, Modal } from '../components/ui'
import { usePeriod } from '../components/Period'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { SHIFT_GROUPS, SHIFT_NUM_KEYS } from '../components/shiftFields'

const baseOpts = { responsive: true, maintainAspectRatio: false }

function ShiftEditModal({ shift, onClose, onSaved }) {
  const toast = useToast()
  const [form, setForm] = useState(() => {
    const o = { work_date: shift.work_date, shift: shift.shift, comment: shift.comment || '' }
    SHIFT_NUM_KEYS.forEach(k => { o[k] = shift[k] ?? 0 })
    return o
  })
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const save = async () => {
    setBusy(true)
    const payload = { work_date: form.work_date, shift: form.shift, comment: form.comment }
    SHIFT_NUM_KEYS.forEach(k => { payload[k] = parseFloat(form[k]) || 0 })
    try {
      await api.updateShift(shift.id, payload)
      toast.ok(`Updated ${form.work_date} · ${form.shift} shift.`)
      onSaved()
    } catch (e) { toast.err(e.message) } finally { setBusy(false) }
  }

  return (
    <Modal title="Edit Shift" sub={`${shift.work_date} · ${shift.shift}`} onClose={onClose}
      footer={<>
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save Changes'}</button>
      </>}>
      <div className="form-grid">
        <div className="fld"><label>Date</label><input type="date" value={form.work_date} onChange={e => set('work_date', e.target.value)} /></div>
        <div className="fld"><label>Shift</label>
          <select value={form.shift} onChange={e => set('shift', e.target.value)}>
            <option>Day</option><option>Afternoon</option><option>Night</option>
          </select>
        </div>
      </div>
      {SHIFT_GROUPS.map(([section, fields]) => (
        <div key={section}>
          <div className="form-section">{section}</div>
          <div className="form-grid">
            {fields.map(([k, lbl]) => (
              <div className="fld" key={k}><label>{lbl}</label>
                <input type="number" value={form[k]} onChange={e => set(k, e.target.value)} />
              </div>
            ))}
          </div>
        </div>
      ))}
      <div className="form-section">Notes</div>
      <div className="fld full"><label>Comments</label>
        <textarea value={form.comment} onChange={e => set('comment', e.target.value)} />
      </div>
    </Modal>
  )
}

export default function Production() {
  const { start, end, rangeKey, control } = usePeriod()
  const { can } = useAuth()
  const toast = useToast()
  const [data, setData] = useState(null)
  const [shifts, setShifts] = useState([])
  const [q, setQ] = useState('')
  const [editing, setEditing] = useState(null)
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    if (!rangeKey || (!start && !end)) return
    setErr('')
    api.summary(start, end).then(setData).catch(e => setErr(e.message))
    api.listShifts(start, end).then(setShifts).catch(e => setErr(e.message))
  }, [rangeKey])

  useEffect(() => { setData(null); load() }, [load])

  const canEdit = can('supervisor')
  const canDelete = can('manager')

  const remove = async (s) => {
    if (!window.confirm(`Delete the ${s.shift} shift on ${s.work_date}?`)) return
    try { await api.deleteShift(s.id); toast.ok('Shift deleted.'); load() }
    catch (e) { toast.err(e.message) }
  }

  if (err) return (
    <div className="main">
      <PageHead title="Production" sub="Output, mix, machine & speed" right={control} />
      <div className="err">{err}</div>
    </div>
  )
  if (!data) return <PageSkeleton kpis={5} cards={4} />

  const days = data.by_day
  const labels = days.map(d => dlabel(d.date))
  const used = Object.entries(data.prod_totals).filter(([, v]) => v > 0).map(([k]) => k)
  const bestDay = [...days].sort((a, b) => b.qty - a.qty)[0] || {}
  const speedDays = data.speed_by_day
  const avgSpeed = speedDays.length ? speedDays.reduce((s, d) => s + d.speed, 0) / speedDays.length : 0
  const hp = data.hp_totals
  const topHP = hp.indexOf(Math.max(...hp))
  const t30 = data.prod_totals.p30s + data.prod_totals.p30l
  const t12 = data.prod_totals.p12n + data.prod_totals.p12hf + data.prod_totals.p12ff

  const ql = q.trim().toLowerCase()
  const rows = [...shifts].reverse().filter(s =>
    !ql || s.work_date.includes(ql) || s.shift.toLowerCase().includes(ql) || (s.comment || '').toLowerCase().includes(ql))

  return (
    <div className="main">
      <PageHead title="Production" sub="Output, mix, machine & speed" right={control} />

      <div className="kpis">
        <Kpi label="30's Trays" value={fmt(t30)} note="main product line" accent={C.amber} />
        <Kpi label="12's Trays" value={fmt(t12)} note="all 12-cell types" accent={C.green} />
        <Kpi label="Best Day" value={fmt(bestDay.qty || 0)} note={(bestDay.date || '').slice(5)} accent={C.blue} />
        <Kpi label="Avg Line Speed" value={fmt(avgSpeed)} unit="/hr" note="products per hour" accent={C.purple} />
        <Kpi label="Top Hot Press" value={fmt(hp[topHP] || 0)} note={`HP${topHP + 1} most used`} accent={C.teal} />
      </div>

      <div className="grid g2">
        <Card span2 title="Production Mix Over Time" sub="Daily trays stacked by product type">
          <div className="chart-box tall">
            {used.length ? (
              <Bar data={{
                labels,
                datasets: used.map(key => ({
                  label: data.prod_labels[key],
                  data: days.map(d => d.prods[key] || 0),
                  backgroundColor: PROD_COLORS[key], maxBarThickness: 22,
                })),
              }}
                options={{ ...baseOpts, plugins: { legend: { labels: { boxWidth: 10, padding: 8, font: { size: 10 } } } }, scales: { x: { ...gridX, stacked: true }, y: { ...gridY, stacked: true } } }} />
            ) : <Empty icon="▤" title="No production in range" />}
          </div>
        </Card>

        <Card title="Hot Press Utilisation" sub="Total trays pressed per machine (HP1–HP6)">
          <div className="chart-box">
            <Bar data={{ labels: ['HP1', 'HP2', 'HP3', 'HP4', 'HP5', 'HP6'], datasets: [{ data: hp, backgroundColor: [C.amber, C.green, C.blue, C.purple, C.teal, C.pink], borderRadius: 4 }] }}
              options={{ ...baseOpts, plugins: { legend: { display: false } }, scales: { x: gridX, y: gridY } }} />
          </div>
        </Card>

        <Card title="Line Speed Trend" sub="Avg products per hour by day">
          <div className="chart-box">
            {speedDays.length ? (
              <Line data={{ labels: speedDays.map(d => dlabel(d.date)), datasets: [{ data: speedDays.map(d => d.speed), borderColor: C.amber, backgroundColor: 'rgba(245,166,35,.12)', fill: true, tension: .35, pointRadius: 0, borderWidth: 2 }] }}
                options={{ ...baseOpts, plugins: { legend: { display: false } }, scales: { x: gridX, y: gridY } }} />
            ) : <Empty icon="◆" title="No speed data" />}
          </div>
        </Card>

        <Card span2 title="Shift Log" sub="Per-shift detail · most recent first"
          right={<div className="search"><span className="s-ic">⌕</span><input placeholder="Search date, shift, note…" value={q} onChange={e => setQ(e.target.value)} /></div>}>
          <div className="tbl-scroll">
            <table>
              <thead><tr>
                <th>Date</th><th>Shift</th><th>Trays</th><th>Speed</th><th>Prod Hrs</th><th>Fuel L</th><th>Down min</th>
                {(canEdit || canDelete) && <th></th>}
              </tr></thead>
              <tbody>
                {rows.map(s => (
                  <tr key={s.id}>
                    <td>{s.work_date}</td>
                    <td><span className={`tag ${s.shift}`}>{s.shift}</span></td>
                    <td>{fmt(s.qty)}</td><td>{fmt(s.speed)}</td><td>{fmt1(s.prod_hours)}</td>
                    <td>{fmt(s.fuel_use)}</td><td>{fmt(s.downtime_min)}</td>
                    {(canEdit || canDelete) && (
                      <td><div className="row-actions">
                        {canEdit && <button className="btn btn-ghost btn-sm" onClick={() => setEditing(s)}>Edit</button>}
                        {canDelete && <button className="btn btn-danger btn-sm" onClick={() => remove(s)}>Delete</button>}
                      </div></td>
                    )}
                  </tr>
                ))}
                {rows.length === 0 && <tr><td colSpan={(canEdit || canDelete) ? 8 : 7} style={{ color: 'var(--dim)' }}>{ql ? 'No shifts match your search.' : 'No shifts logged this period.'}</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {editing && <ShiftEditModal shift={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />}
    </div>
  )
}
