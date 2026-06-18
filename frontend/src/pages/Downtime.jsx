import { useState, useEffect } from 'react'
import { Bar, Doughnut } from 'react-chartjs-2'
import { api } from '../api/client'
import { C, gridX, gridY, fmt, fmt1, dlabel } from '../api/charts'
import { Kpi, Card, PageHead, PageSkeleton, Empty } from '../components/ui'
import { usePeriod } from '../components/Period'

const baseOpts = { responsive: true, maintainAspectRatio: false }
const CAUSE_C = {
  'Cleaning / Washing': C.blue, 'Mold / Mesh Change': C.amber,
  'Maintenance / Repairs': C.red, 'Other': C.purple, 'Unlogged': C.steel,
}

export default function Downtime() {
  const { start, end, rangeKey, control } = usePeriod()
  const [data, setData] = useState(null)
  const [shifts, setShifts] = useState([])

  useEffect(() => {
    if (!rangeKey || (!start && !end)) return
    setData(null)
    api.summary(start, end).then(setData)
    api.listShifts(start, end).then(setShifts)
  }, [rangeKey])

  if (!data) return <PageSkeleton kpis={4} cards={4} />

  const k = data.kpis
  const days = data.by_day
  const causes = Object.entries(data.downtime_causes).map(([n, v]) => ({ n, v })).sort((a, b) => b.v - a.v)
  const maint = data.downtime_causes['Maintenance / Repairs'] || 0
  const worst = [...shifts].sort((a, b) => b.downtime_min - a.downtime_min)[0] || {}
  const shiftOrder = ['Day', 'Afternoon', 'Night']
  const sh = data.by_shift

  return (
    <div className="main">
      <PageHead title="Downtime" sub="Lost time, causes & worst stoppages" right={control} />

      <div className="kpis">
        <Kpi label="Total Downtime" value={fmt1(k.total_downtime_min / 60)} unit="hrs" note={`${fmt(k.total_downtime_min)} minutes`} accent={C.red} />
        <Kpi label="Downtime Rate" value={fmt1(k.downtime_pct)} unit="%" note="of scheduled hours" accent={C.amber} />
        <Kpi label="Worst Stoppage" value={fmt(worst.downtime_min || 0)} unit="min" note={`${worst.work_date || ''} ${worst.shift || ''}`} accent={C.purple} />
        <Kpi label="Maintenance Loss" value={fmt1(maint / 60)} unit="hrs" note="repairs & breakdowns" accent={C.blue} />
      </div>

      <div className="grid g2">
        <Card title="Downtime by Cause" sub="Total minutes lost · classified from shift notes">
          <div className="chart-box">
            {causes.length ? (
              <Doughnut data={{ labels: causes.map(c => c.n), datasets: [{ data: causes.map(c => c.v), backgroundColor: causes.map(c => CAUSE_C[c.n] || C.steel), borderColor: '#161b22', borderWidth: 2 }] }}
                options={{ ...baseOpts, cutout: '58%', plugins: { legend: { position: 'right', labels: { boxWidth: 10, padding: 8, font: { size: 10 } } } } }} />
            ) : <Empty icon="✓" title="No downtime logged" detail="Nothing lost in this period." />}
          </div>
        </Card>

        <Card title="Downtime % by Shift" sub="Lost time as share of scheduled hours">
          <div className="chart-box">
            <Bar data={{ labels: shiftOrder, datasets: [{ data: shiftOrder.map(s => (sh[s] ? sh[s].down_pct : 0)), backgroundColor: [C.amber, C.blue, C.purple], borderRadius: 4 }] }}
              options={{ ...baseOpts, plugins: { legend: { display: false } }, scales: { x: gridX, y: { ...gridY, ticks: { callback: v => v + '%' } } } }} />
          </div>
        </Card>

        <Card span2 title="Daily Downtime Trend" sub="Minutes lost per day · red ≥ 240, amber ≥ 120">
          <div className="chart-box">
            <Bar data={{ labels: days.map(d => dlabel(d.date)), datasets: [{ data: days.map(d => d.down), backgroundColor: days.map(d => d.down >= 240 ? C.red : d.down >= 120 ? C.amber : C.steel), borderRadius: 3, maxBarThickness: 22 }] }}
              options={{ ...baseOpts, plugins: { legend: { display: false } }, scales: { x: gridX, y: gridY } }} />
          </div>
        </Card>

        <Card span2 title="Longest Stoppages" sub="Top downtime events with logged cause">
          <div className="tbl-scroll">
            <table>
              <thead><tr><th>Date</th><th>Shift</th><th>Down min</th><th>Cause / Notes</th></tr></thead>
              <tbody>
                {[...shifts].filter(s => s.downtime_min > 0).sort((a, b) => b.downtime_min - a.downtime_min).slice(0, 15).map(s => (
                  <tr key={s.id}>
                    <td>{s.work_date}</td>
                    <td><span className={`tag ${s.shift}`}>{s.shift}</span></td>
                    <td style={{ color: s.downtime_min >= 240 ? C.red : C.ink, fontWeight: 700 }}>{fmt(s.downtime_min)}</td>
                    <td style={{ textAlign: 'left', color: 'var(--mut)', fontSize: 12 }}>{(s.comment || '').slice(0, 90) || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  )
}
