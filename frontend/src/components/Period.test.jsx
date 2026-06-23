import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { usePeriod, currentMonth } from './Period'

function Host() {
  const { control, start, end } = usePeriod()
  return <div>{control}<span data-testid="range">{`${start}..${end}`}</span></div>
}

describe('usePeriod', () => {
  it('defaults the month picker to the current calendar month', () => {
    render(<Host />)
    // The native month picker is pre-set to this month (YYYY-MM).
    expect(screen.getByDisplayValue(currentMonth())).toBeInTheDocument()
  })

  it('derives start/end as the first..last day of the current month', () => {
    render(<Host />)
    const cur = currentMonth()
    expect(screen.getByTestId('range').textContent).toMatch(new RegExp(`^${cur}-01\\.\\.${cur}-\\d{2}$`))
  })
})
