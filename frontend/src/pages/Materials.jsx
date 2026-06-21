import { useState, useEffect, useCallback } from 'react'
import { api, OFFLINE_QUEUED } from '../api/client'
import { C, fmt, fmt1 } from '../api/charts'
import { Kpi, Card, PageHead, PageSkeleton } from '../components/ui'
import { EntryForm } from '../components/EntryForm'
import { RowEditModal } from '../components/RowEditModal'
import { usePeriod, PeriodPicker } from '../components/Period'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'

const BALE_FIELDS = [
  { key: 'work_date', label: 'Date Received', type: 'date', required: true },
  { key: 'grn', label: 'GRN #', type: 'text', placeholder: 'goods received note' },
  { key: 'weight_kg', label: 'Weight (kg)', type: 'number' },
  { key: 'quantity', label: 'Quantity (bales)', type: 'number' },
]

const STOCK_FIELDS = [
  { key: 'diesel_eom', label: 'Diesel End-of-Month (L)' },
  { key: 'bal_30s', label: "30's Balance" },
  { key: 'bal_12n', label: "12's Normal Balance" },
  { key: 'bal_12ff', label: "12's Full Face Balance" },
  { key: 'bal_12nl', label: "12's NL Balance" },
  { key: 'pallets_wrapped', label: 'Pallets Wrapped' },
  { key: 'bales_used', label: 'Bales Used' },
  { key: 'bales_purchased', label: 'Bales Purchased' },
  { key: 'labels_used', label: 'Labels Used' },
].map(f => ({ ...f, type: 'number' }))

export default function Materials() {
  const { periods, period, setPeriod, start, end, rangeKey } = usePeriod()
  const { can } = useAuth()
  const toast = useToast()
  const [bales, setBales] = useState([])
  const [stock, setStock] = useState(null)
  const [showBale, setShowBale] = useState(false)
  const [editingBale, setEditingBale] = useState(null)
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    if (!period) return
    setErr('')
    api.listBales(start, end).then(setBales).catch(e => setErr(e.message))
    api.listStock().then(setStock).catch(e => setErr(e.message))
  }, [rangeKey])

  useEffect(() => { load() }, [load])

  if (err) return (
    <div className="main">
      <PageHead title="Stock & Bales" sub="Raw material receipts & month-end balances"
        right={<PeriodPicker periods={periods} period={period} setPeriod={setPeriod} />} />
      <div className="err">{err}</div>
    </div>
  )
  if (stock === null) return <PageSkeleton kpis={4} cards={2} />

  const canEditStock = can('supervisor')
  const canWriteBale = can('supervisor')
  const canDeleteStock = can('manager')

  const removeBale = async (id) => {
    if (!window.confirm('Delete this bale receipt?')) return
    try { await api.deleteBale(id); toast.ok('Bale receipt deleted.'); load() }
    catch (e) { toast.err(e.message) }
  }

  const removeStock = async () => {
    if (!window.confirm(`Delete the month-end stock record for ${period}?`)) return
    try { await api.deleteStock(period); toast.ok(`Month-end stock for ${period} deleted.`); load() }
    catch (e) { toast.err(e.message) }
  }

  const totalBaleWeight = bales.reduce((s, b) => s + (b.weight_kg || 0), 0)
  const totalBaleQty = bales.reduce((s, b) => s + (b.quantity || 0), 0)
  const current = stock.find(s => s.period === period)

  const stockDefaults = STOCK_FIELDS.reduce((o, f) => {
    o[f.key] = current ? (current[f.key] ?? 0) : ''
    return o
  }, {})

  return (
    <div className="main">
      <PageHead title="Stock & Bales" sub="Raw material receipts & month-end balances"
        right={<PeriodPicker periods={periods} period={period} setPeriod={setPeriod} />} />

      <div className="kpis">
        <Kpi label="Bale Deliveries" value={fmt(bales.length)} note="receipts this period" accent={C.amber} />
        <Kpi label="Bales Received" value={fmt(totalBaleQty)} note="total bales in" accent={C.green} />
        <Kpi label="Weight Received" value={fmt(totalBaleWeight)} unit="kg" note="raw fibre in" accent={C.blue} />
        <Kpi label="Bales Used (EOM)" value={current ? fmt(current.bales_used) : '—'} note="from month-end stock" accent={C.purple} />
      </div>

      {can('supervisor') && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="entry-head">
            <h3><span className="dot" />Record a Bale Receipt</h3>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowBale(s => !s)}>
              {showBale ? 'Close' : '＋ New receipt'}
            </button>
          </div>
          {showBale && (
            <div style={{ marginTop: 14 }}>
              <EntryForm
                fields={BALE_FIELDS}
                submitLabel="Save Receipt"
                hint="Logs incoming raw fibre bales against a goods-received note."
                onSubmit={async (payload) => {
                  const res = await api.createBale(payload)
                  if (res && res[OFFLINE_QUEUED]) {
                    const m = `Saved offline — bale receipt for ${payload.work_date} will sync when reconnected.`
                    toast.info(m)
                    return { message: m }
                  }
                  load()
                  toast.ok(`Saved bale receipt for ${payload.work_date}.`)
                  return { message: `Saved bale receipt for ${payload.work_date}.` }
                }}
              />
            </div>
          )}
        </div>
      )}

      <div className="grid g2">
        <Card span2 title="Bale Receipt Log" sub="Raw fibre received this period">
          <div className="tbl-scroll" style={{ maxHeight: 300 }}>
            <table>
              <thead><tr><th>Date</th><th>GRN #</th><th>Weight (kg)</th><th>Quantity</th>{canWriteBale && <th></th>}</tr></thead>
              <tbody>
                {[...bales].reverse().map(b => (
                  <tr key={b.id}>
                    <td>{b.work_date}</td>
                    <td style={{ textAlign: 'left' }}>{b.grn || '—'}</td>
                    <td>{b.weight_kg ? fmt(b.weight_kg) : '—'}</td>
                    <td>{b.quantity ? fmt(b.quantity) : '—'}</td>
                    {canWriteBale && (
                      <td><div className="row-actions">
                        <button className="btn btn-ghost btn-sm" onClick={() => setEditingBale(b)}>Edit</button>
                        <button className="btn btn-danger btn-sm" onClick={() => removeBale(b.id)}>Delete</button>
                      </div></td>
                    )}
                  </tr>
                ))}
                {bales.length === 0 && <tr><td colSpan={canWriteBale ? 5 : 4} style={{ color: 'var(--dim)' }}>No bale receipts recorded this period.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>

        <Card span2 title={`Month-End Stock · ${period || ''}`}
          sub={canEditStock ? 'Edit balances for the selected period' : 'Read-only · supervisor access required to edit'}
          right={canDeleteStock && current && <button className="btn btn-danger btn-sm" onClick={removeStock}>Delete record</button>}>
          {canEditStock ? (
            <EntryForm
              key={period + (current ? 'e' : 'n')}
              fields={STOCK_FIELDS.map(f => ({ ...f, default: stockDefaults[f.key] }))}
              submitLabel={current ? 'Update Stock' : 'Save Stock'}
              resetAfter={false}
              hint={current ? 'Updating the existing month-end record.' : 'Creating a new month-end record.'}
              onSubmit={async (payload) => {
                await api.upsertStock(period, { ...payload, period })
                load()
                toast.ok(`Month-end stock saved for ${period}.`)
                return { message: `Month-end stock saved for ${period}.` }
              }}
            />
          ) : (
            <div className="row-flex">
              {current ? STOCK_FIELDS.map(f => (
                <div className="mini" key={f.key}><div className="m-lbl">{f.label}</div><div className="m-val">{fmt1(current[f.key])}</div></div>
              )) : <div className="hint">No month-end record for {period} yet.</div>}
            </div>
          )}
        </Card>
      </div>

      {editingBale && (
        <RowEditModal
          title="Edit Bale Receipt"
          sub={`${editingBale.work_date}${editingBale.grn ? ' · ' + editingBale.grn : ''}`}
          fields={BALE_FIELDS}
          initial={editingBale}
          onClose={() => setEditingBale(null)}
          onSave={async (payload) => {
            await api.updateBale(editingBale.id, payload)
            toast.ok(`Updated bale receipt for ${payload.work_date}.`)
            load()
          }}
        />
      )}
    </div>
  )
}
