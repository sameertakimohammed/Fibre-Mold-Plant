import { useState, useEffect, useCallback } from 'react'
import { Bar } from 'react-chartjs-2'
import { api, OFFLINE_QUEUED } from '../api/client'
import { C, gridX, gridY, fmt, dlabel } from '../api/charts'
import { Kpi, Card, PageHead, PageSkeleton } from '../components/ui'
import { EntryForm } from '../components/EntryForm'
import { usePeriod } from '../components/Period'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'

const baseOpts = { responsive: true, maintainAspectRatio: false }

const DELIVERY_FIELDS = [
  { key: 'work_date', label: 'Date', type: 'date', required: true },
  { key: 'company', label: 'Customer', type: 'text', required: true, placeholder: 'e.g. BULA COLD STORES' },
  { key: 'tray30', label: "30's Trays", type: 'number' },
  { key: 'tray12n', label: "12's Normal", type: 'number' },
  { key: 'tray12ff', label: "12's Full Face", type: 'number' },
  { key: 'pallets', label: 'Pallets', type: 'number' },
  { key: 'comment', label: 'Comment', type: 'textarea', full: true, placeholder: 'optional note' },
]

export default function Deliveries() {
  const { start, end, rangeKey, control } = usePeriod()
  const { can } = useAuth()
  const toast = useToast()
  const [data, setData] = useState(null)
  const [list, setList] = useState([])
  const [showForm, setShowForm] = useState(false)

  const load = useCallback(() => {
    if (!rangeKey || (!start && !end)) return
    api.summary(start, end).then(setData)
    api.listDeliveries(start, end).then(setList)
  }, [rangeKey])

  useEffect(() => { setData(null); load() }, [load])

  const remove = async (id) => {
    if (!window.confirm('Delete this delivery record?')) return
    try { await api.deleteDelivery(id); toast.ok('Delivery deleted.'); load() }
    catch (e) { toast.err(e.message) }
  }

  if (!data) return <PageSkeleton kpis={4} cards={3} />

  const k = data.kpis
  const days = data.by_day
  const dbd = data.deliveries_by_day
  const allDates = [...new Set([...days.map(d => d.date), ...Object.keys(dbd)])].sort()
  const cust = Object.entries(data.deliveries_by_customer).slice(0, 8)
  const canWrite = can('supervisor')
  const canDelete = can('supervisor')

  return (
    <div className="main">
      <PageHead title="Deliveries & Stock" sub="Dispatch flow vs production" right={control} />

      <div className="kpis">
        <Kpi label="30's Delivered" value={fmt(k.deliv_30)} note="dispatched to customers" accent={C.amber} />
        <Kpi label="12's Delivered" value={fmt(k.deliv_12)} note="normal + full face" accent={C.green} />
        <Kpi label="Pallets Shipped" value={fmt(k.deliv_pallets)} note="loaded for dispatch" accent={C.blue} />
        <Kpi label="Deliveries Logged" value={fmt(list.length)} note="recorded this period" accent={C.purple} />
      </div>

      {canWrite && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="entry-head">
            <h3><span className="dot" />Record a Delivery</h3>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowForm(s => !s)}>
              {showForm ? 'Close' : '＋ New delivery'}
            </button>
          </div>
          {showForm && (
            <div style={{ marginTop: 14 }}>
              <EntryForm
                fields={DELIVERY_FIELDS}
                submitLabel="Save Delivery"
                hint="Saves to the central database and updates this page instantly."
                onSubmit={async (payload) => {
                  const res = await api.createDelivery(payload)
                  if (res && res[OFFLINE_QUEUED]) {
                    const m = `Saved offline — delivery for ${payload.company} will sync when reconnected.`
                    toast.info(m)
                    return { message: m }
                  }
                  load()
                  toast.ok(`Saved delivery for ${payload.company}.`)
                  return { message: `Saved delivery for ${payload.company} on ${payload.work_date}.` }
                }}
              />
            </div>
          )}
        </div>
      )}

      <div className="grid g2">
        <Card span2 title="Produced vs Delivered" sub="30's tray flow · production output vs dispatched">
          <div className="chart-box tall">
            <Bar data={{
              labels: allDates.map(dlabel),
              datasets: [
                { label: "Produced (30's)", data: allDates.map(d => { const x = days.find(y => y.date === d); return x ? (x.prods.p30s || 0) + (x.prods.p30l || 0) : 0 }), backgroundColor: C.amber, maxBarThickness: 18 },
                { label: "Delivered (30's)", data: allDates.map(d => dbd[d] || 0), backgroundColor: C.blue, maxBarThickness: 18 },
              ],
            }}
              options={{ ...baseOpts, plugins: { legend: { labels: { boxWidth: 10, font: { size: 10 } } } }, scales: { x: gridX, y: gridY } }} />
          </div>
        </Card>

        <Card title="Deliveries by Customer" sub="Total trays dispatched (all types)">
          <div className="chart-box">
            <Bar data={{ labels: cust.map(c => c[0]), datasets: [{ data: cust.map(c => c[1]), backgroundColor: C.green, borderRadius: 4 }] }}
              options={{ ...baseOpts, indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: gridY, y: { grid: { display: false } } } }} />
          </div>
        </Card>

        <Card title="Delivery Log" sub="All dispatches recorded">
          <div className="tbl-scroll" style={{ maxHeight: 280 }}>
            <table>
              <thead><tr><th>Date</th><th>Customer</th><th>30's</th><th>12's</th><th>Pallets</th>{canDelete && <th></th>}</tr></thead>
              <tbody>
                {list.map(d => (
                  <tr key={d.id}>
                    <td>{d.work_date}</td><td style={{ textAlign: 'left' }}>{d.company}</td>
                    <td>{d.tray30 ? fmt(d.tray30) : '—'}</td>
                    <td>{(d.tray12n + d.tray12ff) ? fmt(d.tray12n + d.tray12ff) : '—'}</td>
                    <td>{d.pallets || '—'}</td>
                    {canDelete && <td><button className="btn btn-danger btn-sm" onClick={() => remove(d.id)}>Delete</button></td>}
                  </tr>
                ))}
                {list.length === 0 && <tr><td colSpan={canDelete ? 6 : 5} style={{ color: 'var(--dim)' }}>No deliveries recorded this period.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  )
}
