import { useState } from 'react'

// Generic inline entry form driven by a field spec.
// field: { key, label, type:'number'|'text'|'date'|'select'|'textarea',
//          options?, required?, full?, default?, step?, placeholder? }
export function EntryForm({ fields, onSubmit, submitLabel = 'Save', hint, resetAfter = true, warn }) {
  const init = () => {
    const o = {}
    fields.forEach(f => {
      o[f.key] = f.default ?? (f.type === 'select' ? (f.options?.[0] ?? '') : '')
    })
    return o
  }
  const [form, setForm] = useState(init)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  // Advisory, non-blocking warnings recomputed live from the current values.
  const warnings = warn ? warn(form) : []

  const submit = async () => {
    for (const f of fields) {
      if (f.required && (form[f.key] === '' || form[f.key] == null)) {
        setMsg({ type: 'err', text: `${f.label} is required` })
        return
      }
    }
    setBusy(true); setMsg(null)
    const payload = {}
    fields.forEach(f => {
      payload[f.key] = f.type === 'number' ? (parseFloat(form[f.key]) || 0) : form[f.key]
    })
    try {
      const res = await onSubmit(payload)
      setMsg({ type: 'ok', text: (res && res.message) || 'Saved — synced to all dashboards.' })
      if (resetAfter) setForm(init())
    } catch (e) {
      setMsg({ type: 'err', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="form-grid">
        {fields.map(f => (
          <div className={`fld ${f.full ? 'full' : ''}`} key={f.key}>
            <label>{f.label}</label>
            {f.type === 'select' ? (
              <select value={form[f.key]} onChange={e => set(f.key, e.target.value)}>
                {f.options.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            ) : f.type === 'textarea' ? (
              <textarea value={form[f.key]} placeholder={f.placeholder} onChange={e => set(f.key, e.target.value)} />
            ) : (
              <input
                type={f.type}
                value={form[f.key]}
                step={f.step}
                placeholder={f.placeholder ?? (f.type === 'number' ? '0' : '')}
                onChange={e => set(f.key, e.target.value)}
              />
            )}
          </div>
        ))}
      </div>
      {warnings.length > 0 && (
        <div className="entry-warn">
          {warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
        </div>
      )}
      <div className="form-actions">
        <button className="btn btn-primary" onClick={submit} disabled={busy}>{busy ? 'Saving…' : submitLabel}</button>
        <button className="btn btn-ghost" onClick={() => { setForm(init()); setMsg(null) }}>Clear</button>
        {hint && <span className="hint">{hint}</span>}
      </div>
      {msg && <div className={msg.type}>{msg.text}</div>}
    </>
  )
}
