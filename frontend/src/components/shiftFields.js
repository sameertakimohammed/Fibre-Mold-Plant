// Shared field layout for the production shift forms (Log Shift + edit modal).
export const SHIFT_GROUPS = [
  ['Output', [
    ['qty', 'Total Trays (Qty)'], ['p30s', "30's Small"], ['p30l', "30's Large"],
    ['p20n', "20's Normal"], ['p12n', "12's Normal"], ['p12hf', "12's Half Face"],
    ['p12ff', "12's Full Face"], ['p4cup', "4's Cup Holder"], ['p2cup', "2's Cup Holder"],
  ]],
  ['Hot Presses (trays each)', [
    ['hp1', 'Hot Press 1'], ['hp2', 'Hot Press 2'], ['hp3', 'Hot Press 3'],
    ['hp4', 'Hot Press 4'], ['hp5', 'Hot Press 5'], ['hp6', 'Hot Press 6'],
  ]],
  ['Fuel · Water · Speed', [
    ['fuel_open', 'Fuel Opening (L)'], ['fuel_close', 'Fuel Closing (L)'], ['fuel_use', 'Fuel Used (L)'],
    ['water_meter', 'Water Meter (m³)'], ['speed', 'Speed (prod/hr)'], ['carton_bales', 'Carton Bales'],
  ]],
  ['Hours & Downtime', [
    ['prod_hours', 'Production Hours'], ['downtime_min', 'Downtime (min)'], ['sched_hours', 'Scheduled Hours'],
    ['clean_min', 'Cleaning (min)'], ['mold_min', 'Mold Change (min)'], ['other_min', 'Other (min)'],
    ['repulped', 'Trays Re-pulped'],
  ]],
]

export const SHIFT_NUM_KEYS = SHIFT_GROUPS.flatMap(([, fields]) => fields.map(([k]) => k))

// --- End-of-shift report sheet (the Team Leader's log) ---------------------
// Extra shift-level fields beyond the numeric production figures above.
// [key, label, type] — type 'number' | 'text' | 'textarea'.
export const SHIFT_EXTRA_FIELDS = [
  ['supervisor', 'Shift Supervisor', 'text'],
  ['staff_count', 'No. of Staff', 'number'],
  ['casual_count', 'No. of Casuals', 'number'],
  ['absenteeism', 'Absenteeism', 'text'],
  ['stock_notes', 'Products in Stock', 'textarea'],
  ['delivery_notes', 'Deliveries', 'textarea'],
]

// Per-machine grid. code = key in the `machines` map; qtyKey = the existing
// numeric field that already holds this machine's quantity (shown read-only as
// context); target = the standard hourly target pre-filled for the operator.
export const SHIFT_MACHINES = [
  { code: 'HGHY', label: 'HGHY (Former)', qtyKey: 'qty', target: 1400 },
  { code: 'HT1', label: 'HT1', qtyKey: 'hp1', target: 250 },
  { code: 'HT2', label: 'HT2', qtyKey: 'hp2', target: 250 },
  { code: 'HT3', label: 'HT3', qtyKey: 'hp3', target: 250 },
  { code: 'HT4', label: 'HT4', qtyKey: 'hp4', target: 250 },
  { code: 'HT5', label: 'HT5', qtyKey: 'hp5', target: 250 },
  { code: 'HT6', label: 'HT6', qtyKey: 'hp6', target: 250 },
  { code: 'LABEL', label: 'Label Applicator', qtyKey: 'labelling', target: 720 },
]

// Per-machine attribute columns: [key, label, type].
export const MACHINE_ATTRS = [
  ['paid_hours', 'Paid Hrs', 'number'],
  ['run_hours', 'Run Hrs', 'number'],
  ['target_per_hr', 'Target /hr', 'number'],
  ['actual_per_hr', 'Actual /hr', 'number'],
  ['operators', 'Operator(s)', 'text'],
  ['product_detail', 'Product Detail', 'text'],
]

// A blank machines map with the standard hourly targets pre-filled.
export const emptyMachines = () => {
  const m = {}
  SHIFT_MACHINES.forEach(({ code, target }) => {
    m[code] = { paid_hours: '', run_hours: '', target_per_hr: target, actual_per_hr: '', operators: '', product_detail: '' }
  })
  return m
}
