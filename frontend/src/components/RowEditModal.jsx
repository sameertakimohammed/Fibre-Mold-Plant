import { useState } from 'react'
import { Modal } from './ui'

// Generic edit modal driven by the SAME field spec the EntryForm uses, so the
// "Record a …" form and the "Edit" modal stay in lock-step. Self-contained
// (its own form state) to match the existing ShiftEditModal pattern and avoid
// setState-after-unmount on close.
//
// props:
//   fields   — [{ key, label, type, options?, required?, full?, step? }]
//   initial  — the row being edited (values prefill the form)
//   onSave   — async (payload) => {}  (do the API call + toast + reload here)
//   onClose  — close the modal
//   warn     — optional (values) => string[] advisory warnings
export function RowEditModal({ title, sub, fields, initial, onSave, onClose, warn, submitLabel = 'Save Changes' }) {
  const [form, setForm] = useState(() => {
    const o = {}
    fields.forEach(f => {
      o[f.key] = initial?.[f.key] ?? f.default ?? (f.type === 'select' ? (f.options?.[0] ?? '') : '')
    })
    return o
  })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const warnings = warn ? warn(form) : []

  const save = async () => {
    for (const f of fields) {
      if (f.required && (form[f.key] === '' || form[f.key] == null)) {
        setErr(`${f.label} is required`)
        return
      }
    }
    setBusy(true); setErr('')
    const payload = {}
    fields.forEach(f => { payload[f.key] = f.type === 'number' ? (parseFloat(form[f.key]) || 0) : form[f.key] })
    try {
      await onSave(payload)
      onClose()               // success → unmount; no further setState here
    } catch (e) {
      setErr(e.message); setBusy(false)
    }
  }

  return (
    <Modal title={title} sub={sub} onClose={onClose}
      footer={<>
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? 'Saving…' : submitLabel}</button>
      </>}>
      <div className="form-grid">
        {fields.map(f => (
          <div className={`fld ${f.full ? 'full' : ''}`} key={f.key}>
            <label>{f.label}</label>
            {f.type === 'select' ? (
              <select value={form[f.key]} onChange={e => set(f.key, e.target.value)}>
                {f.options.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            ) : f.type === 'textarea' ? (
              <textarea value={form[f.key]} onChange={e => set(f.key, e.target.value)} />
            ) : (
              <input type={f.type} value={form[f.key]} step={f.step}
                onChange={e => set(f.key, e.target.value)} />
            )}
          </div>
        ))}
      </div>
      {warnings.length > 0 && (
        <div className="entry-warn">{warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}</div>
      )}
      {err && <div className="err">{err}</div>}
    </Modal>
  )
}
