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
