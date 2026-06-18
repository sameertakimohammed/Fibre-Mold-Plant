import { useState, useEffect, useCallback } from 'react'
import { api, OFFLINE_QUEUED } from '../api/client'
import { C, fmt, fmt1 } from '../api/charts'
import { Kpi, Card, PageHead, PageSkeleton } from '../components/ui'
import { EntryForm } from '../components/EntryForm'
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

  const load = useCallback(() => {
    if (!period) return
    api.listBales(start, end).then(setBales)
    api.listStock().then(setStock)
  }, [rangeKey])

  useEffect(() => { load() }, [load])

  if (stock === null) return <PageSkeleton kpis={4} cards={2} />

  const canEditStock = can('supervisor')
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
              <thead><tr><th>Date</th><th>GRN #</th><th>Weight (kg)</th><th>Quantity</th></tr></thead>
              <tbody>
                {[...bales].reverse().map(b => (
                  <tr key={b.id}>
                    <td>{b.work_date}</td>
                    <td style={{ textAlign: 'left' }}>{b.grn || '—'}</td>
                    <td>{b.weight_kg ? fmt(b.weight_kg) : '—'}</td>
                    <td>{b.quantity ? fmt(b.quantity) : '—'}</td>
                  </tr>
                ))}
                {bales.length === 0 && <tr><td colSpan={4} style={{ color: 'var(--dim)' }}>No bale receipts recorded this period.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>

        <Card span2 title={`Month-End Stock · ${period || ''}`} sub={canEditStock ? 'Edit balances for the selected period' : 'Read-only · supervisor access required to edit'}>
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
    </div>
  )
}
