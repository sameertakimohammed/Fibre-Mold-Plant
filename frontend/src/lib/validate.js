// Advisory data-entry checks. These NEVER block a save — the plant's real data
// has legitimate small mismatches — they just flag likely typos at entry time so
// an operator can double-check. The backend keeps the hard guards (no negatives,
// downtime <= scheduled, etc.); this layer is purely a heads-up.

const PRODUCT_KEYS = ['p30s', 'p30l', 'p20n', 'p12n', 'p12hf', 'p12ff', 'p4cup', 'p2cup']

const num = (v) => {
  const n = parseFloat(v)
  return Number.isFinite(n) ? n : 0
}
const fmt = (n) => Math.round(n).toLocaleString()
// percentage difference of a vs b, relative to the larger magnitude
const relDiff = (a, b) => {
  const denom = Math.max(Math.abs(a), Math.abs(b))
  return denom === 0 ? 0 : Math.abs(a - b) / denom
}

// Tolerance before we bother the operator (5% of the larger figure).
const TOL = 0.05

// Warnings for a production-shift entry (Log Shift + edit modal).
export function shiftWarnings(values = {}) {
  const out = []
  const qty = num(values.qty)

  // 1) Product-type breakdown should roughly add up to the total trays.
  const prodSum = PRODUCT_KEYS.reduce((s, k) => s + num(values[k]), 0)
  if (qty > 0 && prodSum > 0 && relDiff(prodSum, qty) > TOL) {
    out.push(`Product types add up to ${fmt(prodSum)}, but Total Trays is ${fmt(qty)}.`)
  }

  // 2) Fuel used should reconcile with the opening minus closing tank reading.
  const open = num(values.fuel_open)
  const close = num(values.fuel_close)
  const use = num(values.fuel_use)
  if (open > 0 && close > 0 && use > 0 && open >= close) {
    const expected = open - close
    if (expected > 0 && relDiff(use, expected) > TOL) {
      out.push(`Fuel Used (${fmt(use)} L) doesn't match Opening − Closing (${fmt(expected)} L).`)
    }
  }

  return out
}

// Warnings for a fuel-dip entry (Fuel page).
export function fuelDipWarnings(values = {}) {
  const out = []
  const open = num(values.open_dip)
  const close = num(values.close_dip)
  const received = num(values.received)
  const usage = num(values.actual_usage)

  // Usage should reconcile with opening − closing + received.
  if (open > 0 && close >= 0 && usage > 0) {
    const expected = open - close + received
    if (expected > 0 && relDiff(usage, expected) > TOL) {
      out.push(`Actual Usage (${fmt(usage)} L) doesn't match Opening − Closing + Received (${fmt(expected)} L).`)
    }
  }
  return out
}
