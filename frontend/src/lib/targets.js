// Shared KPI-target helpers used by the Dashboard (editor + cards) and the
// Reports preview. The backend (routers/targets) is the source of truth for the
// metric keys and which are volume vs rate; this mirrors them for the UI.
import { fmt } from '../api/charts'

// `lower` = lower-is-better; `kind` is 'volume' (a per-period total: trays,
// litres) or 'rate' (a ratio that's the same goal at every cadence).
export const TARGET_METRICS = [
  { key: 'prod_30', label: "30's Trays", lower: false, unit: '', kind: 'volume' },
  { key: 'prod_12', label: "12's Cartons", lower: false, unit: '', kind: 'volume' },
  { key: 'diesel', label: 'Diesel used', lower: true, unit: ' L', kind: 'volume' },
  { key: 'fuel_eff', label: 'Fuel efficiency (L/1k)', lower: true, unit: '', kind: 'rate' },
  { key: 'downtime_pct', label: 'Downtime', lower: true, unit: '%', kind: 'rate' },
  { key: 'repulp_rate', label: 'Reject rate', lower: true, unit: '%', kind: 'rate' },
]

// daily = normal weekday · weekly = Mon–Fri · saturday = reduced Sat run · monthly
export const PERIODS = ['daily', 'weekly', 'saturday', 'monthly']

// Which analytics-summary `kpis` field holds the actual for each target metric
// (diesel's actual is the total fuel burned in litres).
const ACTUAL_FIELD = {
  prod_30: 'prod_30', prod_12: 'prod_12', diesel: 'total_fuel',
  fuel_eff: 'fuel_eff', downtime_pct: 'downtime_pct', repulp_rate: 'repulp_rate',
}

export function actualForMetric(metricKey, kpis) {
  const f = ACTUAL_FIELD[metricKey]
  return kpis && f ? kpis[f] : undefined
}

export const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s)

// Build the { text, pct, met } object the Kpi target bar renders, or null.
// `period` (daily|weekly|monthly|null) just labels which cadence is in force.
export function buildTarget(actual, targetVal, lower, unit = '', period = null) {
  if (targetVal == null || targetVal <= 0) return null
  const attain = lower
    ? (actual > 0 ? (targetVal / actual) * 100 : 100)
    : (actual / targetVal) * 100
  const met = lower ? actual <= targetVal : actual >= targetVal
  const lbl = period ? `${cap(period)} target` : 'Target'
  return { pct: attain, met, text: `${lbl} ${fmt(targetVal)}${unit} · ${Math.round(attain)}%` }
}
