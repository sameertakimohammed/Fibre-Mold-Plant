import {
  Chart, CategoryScale, LinearScale, BarElement, LineElement, PointElement,
  ArcElement, Tooltip, Legend, Filler,
} from 'chart.js'

Chart.register(
  CategoryScale, LinearScale, BarElement, LineElement, PointElement,
  ArcElement, Tooltip, Legend, Filler
)
Chart.defaults.color = '#8b97a5'
Chart.defaults.font.family = "'JetBrains Mono',monospace"
Chart.defaults.font.size = 11
Chart.defaults.borderColor = '#2a323d'

export const C = {
  amber: '#f5a623', green: '#3fb950', red: '#f0556d', blue: '#58a6ff',
  purple: '#bc8cff', teal: '#2dd4bf', pink: '#f472b6', steel: '#7d8da0',
  line: '#2a323d', mut: '#8b97a5', ink: '#e8edf2',
}

export const PROD_COLORS = {
  p30s: C.amber, p30l: C.green, p20n: C.blue, p12n: C.purple,
  p12hf: C.teal, p12ff: C.pink, p4cup: C.steel, p2cup: C.red,
}

export const gridX = { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 16 } }
export const gridY = {
  grid: { color: 'rgba(42,50,61,.5)' },
  ticks: { callback: v => (v >= 1000 ? v / 1000 + 'k' : v) },
}
export const fmt = n => Math.round(n || 0).toLocaleString()
export const fmt1 = n => (Math.round((n || 0) * 10) / 10).toLocaleString()
export const dlabel = d => (d ? d.slice(5) : '')
