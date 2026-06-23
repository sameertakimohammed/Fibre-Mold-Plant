import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Kpi } from './ui'

describe('Kpi target bar', () => {
  it('renders nothing extra without a target', () => {
    const { container } = render(<Kpi label="Avg / Day" value="8,000" />)
    expect(container.querySelector('.k-target')).toBeNull()
  })

  it('marks an unmet target', () => {
    const { container } = render(
      <Kpi label="Avg / Day" value="8,000" target={{ text: 'Target 9,000 · 89%', pct: 89, met: false }} />
    )
    const t = container.querySelector('.k-target')
    expect(t).not.toBeNull()
    expect(t.className).toContain('miss')
    expect(screen.getByText(/Target 9,000/)).toBeInTheDocument()
  })

  it('marks a met target', () => {
    const { container } = render(
      <Kpi label="Avg / Day" value="9,500" target={{ text: 'Target 9,000 · 105%', pct: 105, met: true }} />
    )
    expect(container.querySelector('.k-target').className).toContain('met')
  })
})
