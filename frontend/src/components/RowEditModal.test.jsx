import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { RowEditModal } from './RowEditModal'

const FIELDS = [
  { key: 'work_date', label: 'Date', type: 'date', required: true },
  { key: 'company', label: 'Customer', type: 'text', required: true },
  { key: 'tray30', label: "30's", type: 'number' },
]

describe('RowEditModal', () => {
  it('prefills from the initial row', () => {
    render(<RowEditModal title="Edit" fields={FIELDS}
      initial={{ work_date: '2026-05-01', company: 'ACME', tray30: 12 }}
      onSave={vi.fn()} onClose={vi.fn()} />)
    expect(screen.getByDisplayValue('ACME')).toBeInTheDocument()
    expect(screen.getByDisplayValue('12')).toBeInTheDocument()
  })

  it('saves a numeric-parsed payload and then closes', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined)
    const onClose = vi.fn()
    render(<RowEditModal title="Edit" fields={FIELDS}
      initial={{ work_date: '2026-05-01', company: 'ACME', tray30: 12 }}
      onSave={onSave} onClose={onClose} />)

    fireEvent.click(screen.getByText('Save Changes'))
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1))
    // number field arrives as a number, not a string
    expect(onSave.mock.calls[0][0]).toEqual({ work_date: '2026-05-01', company: 'ACME', tray30: 12 })
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('blocks save and shows an error when a required field is empty', async () => {
    const onSave = vi.fn()
    render(<RowEditModal title="Edit" fields={FIELDS}
      initial={{ work_date: '2026-05-01', company: '', tray30: 0 }}
      onSave={onSave} onClose={vi.fn()} />)
    fireEvent.click(screen.getByText('Save Changes'))
    expect(await screen.findByText(/Customer is required/)).toBeInTheDocument()
    expect(onSave).not.toHaveBeenCalled()
  })

  it('surfaces a save error instead of closing', async () => {
    const onSave = vi.fn().mockRejectedValue(new Error('server said no'))
    const onClose = vi.fn()
    render(<RowEditModal title="Edit" fields={FIELDS}
      initial={{ work_date: '2026-05-01', company: 'ACME', tray30: 1 }}
      onSave={onSave} onClose={onClose} />)
    fireEvent.click(screen.getByText('Save Changes'))
    expect(await screen.findByText(/server said no/)).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('renders advisory warnings from the warn prop', () => {
    render(<RowEditModal title="Edit" fields={FIELDS}
      initial={{ work_date: '2026-05-01', company: 'ACME', tray30: 1 }}
      warn={() => ['check this number']}
      onSave={vi.fn()} onClose={vi.fn()} />)
    expect(screen.getByText(/check this number/)).toBeInTheDocument()
  })
})
