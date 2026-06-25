import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bar, Doughnut } from 'react-chartjs-2'
import { api } from '../api/client'
import { C, PROD_COLORS, gridX, gridY, fmt, fmt1, dlabel } from '../api/charts'
import { Kpi, Card, PageHead, PageSkeleton, Empty } from '../components/ui'
import { usePeriod } from '../components/Period'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { buildTarget } from '../lib/targets'

const baseOpts = { responsive: true, maintainAspectRatio: false }
const INS_IC = { bad: '✕', warn: '⚠', good: '✓', info: 'ℹ' }

export default function Dashboard() {
  const { start, end, rangeKey, control } = usePeriod()
  const { can } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!rangeKey || (!start && !end)) return
    setData(null); setErr('')
    api.summary(start, end).then(setData).catch(e => setErr(e.message))
  }, [rangeKey])

  const exportReport = async () => {
    setBusy(true)
    try {
      await api.downloadReport(start, end)
      toast.ok('Report downloaded.')
    } catch (e) {
      toast.err(e.message)
    } finally { setBusy(false) }
  }

  const exportBtn = (
    <>
      {control}
      {can('manager') && (
        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/targets')}>
          ◎ Targets
        </button>
      )}
      <button className="btn btn-ghost btn-sm" onClick={exportReport} disabled={busy || !data}>
        {busy ? 'Preparing…' : '⤓ Export'}
      </button>
    </>
  )

  if (err) return (
    <div className="main">
      <PageHead title="Plant Overview" sub="Golden Manufacturers · Recycling Department" right={exportBtn} />
      <div className="err">{err}</div>
    </div>
  )
  if (!data) return <PageSkeleton kpis={6} cards={3} />

  const k = data.kpis
  const d = data.deltas || {}
  const days = data.by_day
  const labels = days.map(x => dlabel(x.date))
  const qtySpark = days.map(x => x.qty)
  const fuelSpark = days.filter(x => x.fuel > 0).map(x => x.eff)

  const mix = Object.entries(data.prod_totals)
    .map(([key, v]) => ({ key, v, name: data.prod_labels[key], c: PROD_COLORS[key] }))
    .filter(p => p.v > 0).sort((a, b) => b.v - a.v)

  const shiftOrder = ['Day', 'Afternoon', 'Night']
  const sh = data.by_shift
  const avgLine = k.avg_per_day || 0
  const tg = data.targets || {}
  const tp = data.target_period   // 'daily' | 'weekly' | 'monthly' | null
  const fc = data.forecast

  return (
    <div className="main">
      <PageHead title="Plant Overview" sub="Golden Manufacturers · Recycling Department" right={exportBtn} />

      <div className="kpis">
        <Kpi label="Total Trays" value={fmt(k.total_qty)} note={`${k.active_days} active days`} accent={C.amber}
          delta={{ value: d.total_qty }} spark={qtySpark} />
        <Kpi label="30's Trays" value={fmt(k.prod_30)} note="formed this period" accent={C.green}
          target={buildTarget(k.prod_30, tg.prod_30, false, '', tp)} />
        <Kpi label="12's Cartons" value={fmt(k.prod_12)} note="formed this period" accent={C.teal}
          target={buildTarget(k.prod_12, tg.prod_12, false, '', tp)} />
        <Kpi label="Fuel Burned" value={fmt(k.total_fuel)} unit="L" accent={C.blue}
          note={`${fmt1(k.fuel_eff)} L/1k${tg.fuel_eff ? ` · target ${fmt1(tg.fuel_eff)}` : ''}`}
          delta={{ value: d.fuel_eff, betterWhenLower: true }} sparkColor={C.blue} spark={fuelSpark}
          target={buildTarget(k.total_fuel, tg.diesel, true, ' L', tp)} />
        <Kpi label="Downtime" value={fmt1(k.total_downtime_min / 60)} unit="hrs" note={`${fmt1(k.downtime_pct)}% of scheduled`} accent={C.red}
          delta={{ value: d.downtime_pct, suffix: 'pp', betterWhenLower: true }}
          target={buildTarget(k.downtime_pct, tg.downtime_pct, true, '%', tp)} />
        <Kpi label="Re-pulped" value={fmt(k.total_repulped)} note={`${fmt1(k.repulp_rate)}% reject rate`} accent={C.purple}
          delta={{ value: d.total_repulped, betterWhenLower: true }}
          target={buildTarget(k.repulp_rate, tg.repulp_rate, true, '%', tp)} />
      </div>

      {d.prev_label && <div className="banner" style={{ marginTop: -6 }}>Trend vs previous period ({d.prev_label})</div>}

      {fc && (
        <div className="banner" style={{ marginTop: -6 }}>
          Projected output this period: <strong>{fmt(fc.projected_qty)}</strong> trays
          {' '}· run-rate from {fc.elapsed_days} of {fc.total_days} days (as of {fc.as_of})
        </div>
      )}

      <div className="grid g2">
        <Card span2 title="Daily Production Output" sub={`Total trays per day · dashed line = ${fmt(avgLine)} avg`}>
          <div className="chart-box tall">
            <Bar data={{ labels, datasets: [
              { label: 'Trays', data: days.map(x => x.qty), backgroundColor: C.amber, borderRadius: 3, maxBarThickness: 22 },
              { label: 'Average', type: 'line', data: days.map(() => avgLine), borderColor: C.steel, borderDash: [6, 5], borderWidth: 1.5, pointRadius: 0, fill: false },
            ] }}
              options={{ ...baseOpts, plugins: { legend: { display: false } }, scales: { x: gridX, y: gridY } }} />
          </div>
        </Card>

        <Card title="Needs Attention" sub="Auto-flagged from this period's data">
          <div className="insights">
            {data.insights.map((ins, i) => (
              <div key={i} className={`insight ${ins.level}`}>
                <span className="i-ic">{INS_IC[ins.level] || 'ℹ'}</span>
                <div>
                  <div className="i-t">{ins.title}</div>
                  {ins.detail && <div className="i-d">{ins.detail}</div>}
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Output by Product Type" sub="Share of total trays">
          <div className="chart-box">
            {mix.length ? (
              <Doughnut data={{ labels: mix.map(p => p.name), datasets: [{ data: mix.map(p => p.v), backgroundColor: mix.map(p => p.c), borderColor: '#161b22', borderWidth: 2 }] }}
                options={{ ...baseOpts, cutout: '58%', plugins: { legend: { position: 'right', labels: { boxWidth: 10, padding: 8, font: { size: 10 } } } } }} />
            ) : <Empty icon="▤" title="No production yet" detail="Log a shift to see the product mix." />}
          </div>
        </Card>

        <Card title="Shift Performance" sub="Avg trays & downtime by shift">
          <div className="chart-box">
            <Bar data={{
              labels: shiftOrder,
              datasets: [
                { label: 'Avg trays', data: shiftOrder.map(s => (sh[s] ? sh[s].q / (sh[s].n || 1) : 0)), backgroundColor: C.green, borderRadius: 3, yAxisID: 'y' },
                { label: 'Avg downtime (min)', data: shiftOrder.map(s => (sh[s] ? sh[s].d / (sh[s].n || 1) : 0)), backgroundColor: C.red, borderRadius: 3, yAxisID: 'y1' },
              ],
            }}
              options={{ ...baseOpts, plugins: { legend: { labels: { boxWidth: 10, font: { size: 10 } } } }, scales: { x: gridX, y: { position: 'left', ...gridY }, y1: { position: 'right', grid: { display: false }, ticks: { color: C.red } } } }} />
          </div>
        </Card>
      </div>

    </div>
  )
}
