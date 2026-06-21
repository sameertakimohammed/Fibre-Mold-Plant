import { describe, it, expect } from 'vitest'
import { shiftWarnings, fuelDipWarnings } from './validate'

describe('shiftWarnings', () => {
  it('no warnings on an empty/zero entry', () => {
    expect(shiftWarnings({})).toEqual([])
  })

  it('no warning when product types match the total within tolerance', () => {
    const v = { qty: 1000, p30s: 600, p12n: 405 } // 1005 vs 1000 -> 0.5%
    expect(shiftWarnings(v)).toEqual([])
  })

  it('warns when product types diverge from the total', () => {
    const v = { qty: 1000, p30s: 500, p12n: 200 } // 700 vs 1000 -> 30%
    const w = shiftWarnings(v)
    expect(w.length).toBe(1)
    expect(w[0]).toMatch(/Product types/)
  })

  it('warns when fuel used does not match opening minus closing', () => {
    const v = { qty: 0, fuel_open: 1000, fuel_close: 600, fuel_use: 100 } // expected 400
    const w = shiftWarnings(v)
    expect(w.some(x => /Fuel Used/.test(x))).toBe(true)
  })

  it('does not warn on a refuel (closing > opening)', () => {
    const v = { fuel_open: 200, fuel_close: 900, fuel_use: 100 }
    expect(shiftWarnings(v).some(x => /Fuel Used/.test(x))).toBe(false)
  })

  it('tolerates string inputs (form fields are strings)', () => {
    const v = { qty: '1000', p30s: '500', p12n: '200' }
    expect(shiftWarnings(v).length).toBe(1)
  })
})

describe('fuelDipWarnings', () => {
  it('no warning when usage reconciles with open - close + received', () => {
    const v = { open_dip: 1000, close_dip: 400, received: 0, actual_usage: 600 }
    expect(fuelDipWarnings(v)).toEqual([])
  })

  it('accounts for fuel received during the period', () => {
    const v = { open_dip: 1000, close_dip: 400, received: 500, actual_usage: 1100 }
    expect(fuelDipWarnings(v)).toEqual([])
  })

  it('warns when usage is inconsistent', () => {
    const v = { open_dip: 1000, close_dip: 400, received: 0, actual_usage: 200 } // expected 600
    expect(fuelDipWarnings(v).length).toBe(1)
  })
})
