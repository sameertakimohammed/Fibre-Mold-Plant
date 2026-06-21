import { useState, useEffect, useCallback } from 'react'
import { Bar, Line } from 'react-chartjs-2'
import { api, OFFLINE_QUEUED } from '../api/client'
import { C, gridX, gridY, fmt, fmt1, dlabel } from '../api/charts'
import { Kpi, Card, PageHead, PageSkeleton, Empty } from '../components/ui'
import { EntryForm } from '../components/EntryForm'
import { RowEditModal } from '../components/RowEditModal'
import { usePeriod } from '../components/Period'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { fuelDipWarnings } from '../lib/validate'

const baseOpts = { responsive: true, maintainAspectRatio: false }

const DIP_FIELDS = [
  { key: 'work_date', label: 'Date', type: 'date', required: true },
  { key: 'shift', label: 'Shift', type: 'select', options: ['Day', 'Afternoon', 'Night'] },
  { key: 'open_dip', label: 'Opening Dip (L)', type: 'number' },
  { key: 'close_dip', label: 'Closing Dip (L)', type: 'number' },
  { key: 'actual_usage', label: 'Actual Usage (L)', type: 'number' },
  { key: 'received', label: 'Diesel Received (L)', type: 'number' },
  { key: 'note', label: 'Note', type: 'textarea', full: true, placeholder: 'optional' },
]

export default function Fuel() {
  const { start, end, rangeKey, control } = usePeriod()
  const { can } = useAuth()
  const toast = useToast()
  const [data, setData] = useState(null)
  const [dips, setDips] = useState([])
  const [price, setPrice] = useState(2.4)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    if (!rangeKey || (!start && !end)) return
    setErr('')
    api.summary(start, end).then(setData).catch(e => setErr(e.message))
    api.listFuelDips(start, end).then(setDips).catch(e => setErr(e.message))
  }, [rangeKey])

  useEffect(() => { setData(null); load() }, [load])

  const canWrite = can('supervisor')

  const removeDip = async (id) => {
    if (!window.confirm('Delete this fuel-dip reading?')) return
    try { await api.deleteFuelDip(id); toast.ok('Fuel dip deleted.'); load() }
    catch (e) { toast.err(e.message) }
  }

  if (err) return (
    <div className="main">
      <PageHead title="Fuel & Energy" sub="Diesel consumption, efficiency & cost" right={control} />
      <div className="err">{err}</div>
    </div>
  )
  if (!data) return <PageSkeleton kpis={4} cards={3} />

  const k = data.kpis
  const days = data.by_day
  const fdays = days.filter(d => d.fuel > 0)
  const labels = days.map(d => dlabel(d.date))
  const bestEff = [...fdays].filter(d => d.eff > 0).sort((a, b) => a.eff - b.eff)[0]

  const totalCost = k.total_fuel * price
  const perK = k.total_qty ? (totalCost / k.total_qty * 1000) : 0
  const perDay = totalCost / (fdays.length || 1)

  return (
    <div className="main">
      <PageHead title="Fuel & Energy" sub="Diesel consumption, efficiency & cost" right={control} />

      <div className="kpis">
        <Kpi label="Total Diesel" value={fmt(k.total_fuel)} unit="L" note="consumed this period" accent={C.blue} />
        <Kpi label="Avg / Day" value={fmt(k.total_fuel / (fdays.length || 1))} unit="L" note="litres per active day" accent={C.amber} />
        <Kpi label="Efficiency" value={fmt1(k.fuel_eff)} unit="L/1k" note="litres per 1,000 trays" accent={C.green} />
        <Kpi label="Best Day" value={bestEff ? fmt1(bestEff.eff) : '—'} unit="L/1k" note={bestEff ? bestEff.date.slice(5) : ''} accent={C.purple} />
      </div>

      {can('supervisor') && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="entry-head">
            <h3><span className="dot" />Record a Fuel Dip</h3>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowForm(s => !s)}>
              {showForm ? 'Close' : '＋ New dip reading'}
            </button>
          </div>
          {showForm && (
            <div style={{ marginTop: 14 }}>
              <EntryForm
                fields={DIP_FIELDS}
                submitLabel="Save Dip"
                warn={fuelDipWarnings}
                hint="Tank dip readings — recorded separately from the shift fuel figures."
                onSubmit={async (payload) => {
                  const res = await api.createFuelDip(payload)
                  if (res && res[OFFLINE_QUEUED]) {
                    return { message: `Saved offline — ${payload.shift} dip for ${payload.work_date} will sync when reconnected.` }
                  }
                  load()
                  return { message: `Saved ${payload.shift} dip for ${payload.work_date}.` }
                }}
              />
            </div>
          )}
        </div>
      )}

      <div className="grid g2">
        <Card span2 title="Daily Fuel Consumption" sub="Diesel litres burned per day">
          <div className="chart-box tall">
            <Bar data={{ labels, datasets: [{ data: days.map(d => d.fuel), backgroundColor: C.blue, borderRadius: 3, maxBarThickness: 22 }] }}
              options={{ ...baseOpts, plugins: { legend: { display: false } }, scales: { x: gridX, y: gridY } }} />
          </div>
        </Card>

        <Card title="Fuel Efficiency" sub="Litres per 1,000 trays · lower is better">
          <div className="chart-box">
            <Line data={{ labels: fdays.map(d => dlabel(d.date)), datasets: [{ data: fdays.map(d => d.eff), borderColor: C.green, backgroundColor: 'rgba(63,185,80,.12)', fill: true, tension: .3, pointRadius: 0, borderWidth: 2 }] }}
              options={{ ...baseOpts, plugins: { legend: { display: false } }, scales: { x: gridX, y: gridY } }} />
          </div>
        </Card>

        <Card title="Cost Estimate" sub="Adjust diesel price to model spend">
          <div className="fld" style={{ marginBottom: 16 }}>
            <label>Diesel price (FJD / litre)</label>
            <input type="number" value={price} step="0.05" min="0" onChange={e => setPrice(parseFloat(e.target.value) || 0)} />
          </div>
          <div className="row-flex">
            <div className="mini"><div className="m-lbl">Period Fuel Cost</div><div className="m-val">${fmt(totalCost)}</div></div>
            <div className="mini"><div className="m-lbl">Cost / 1k Trays</div><div className="m-val">${fmt1(perK)}</div></div>
            <div className="mini"><div className="m-lbl">Avg / Day</div><div className="m-val">${fmt(perDay)}</div></div>
          </div>
        </Card>

        <Card span2 title="Fuel Dip Log" sub="Manual tank readings recorded this period">
          <div className="tbl-scroll" style={{ maxHeight: 300 }}>
            <table>
              <thead><tr><th>Date</th><th>Shift</th><th>Open L</th><th>Close L</th><th>Usage L</th><th>Received L</th><th>Note</th>{canWrite && <th></th>}</tr></thead>
              <tbody>
                {[...dips].reverse().map(d => (
                  <tr key={d.id}>
                    <td>{d.work_date}</td>
                    <td><span className={`tag ${d.shift}`}>{d.shift}</span></td>
                    <td>{d.open_dip ? fmt(d.open_dip) : '—'}</td>
                    <td>{d.close_dip ? fmt(d.close_dip) : '—'}</td>
                    <td>{d.actual_usage ? fmt(d.actual_usage) : '—'}</td>
                    <td>{d.received ? fmt(d.received) : '—'}</td>
                    <td style={{ textAlign: 'left', color: 'var(--mut)', fontSize: 12 }}>{d.note || '—'}</td>
                    {canWrite && (
                      <td><div className="row-actions">
                        <button className="btn btn-ghost btn-sm" onClick={() => setEditing(d)}>Edit</button>
                        <button className="btn btn-danger btn-sm" onClick={() => removeDip(d.id)}>Delete</button>
                      </div></td>
                    )}
                  </tr>
                ))}
                {dips.length === 0 && <tr><td colSpan={canWrite ? 8 : 7} style={{ color: 'var(--dim)' }}>No dip readings recorded this period.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {editing && (
        <RowEditModal
          title="Edit Fuel Dip"
          sub={`${editing.work_date} · ${editing.shift}`}
          fields={DIP_FIELDS}
          initial={editing}
          warn={fuelDipWarnings}
          onClose={() => setEditing(null)}
          onSave={async (payload) => {
            await api.updateFuelDip(editing.id, payload)
            toast.ok(`Updated ${payload.shift} dip for ${payload.work_date}.`)
            load()
          }}
        />
      )}
    </div>
  )
}
