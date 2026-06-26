import { useState } from 'react'
import { api, OFFLINE_QUEUED } from '../api/client'
import { PageHead } from '../components/ui'
import {
  SHIFT_GROUPS, SHIFT_NUM_KEYS, SHIFT_EXTRA_FIELDS, SHIFT_MACHINES, MACHINE_ATTRS, emptyMachines,
} from '../components/shiftFields'
import { useToast } from '../context/ToastContext'
import { shiftWarnings } from '../lib/validate'

const NUM_ATTRS = new Set(MACHINE_ATTRS.filter(([, , t]) => t === 'number').map(([k]) => k))

const empty = () => {
  const o = { work_date: '', shift: 'Day', comment: '', sched_hours: 8 }
  SHIFT_NUM_KEYS.forEach(k => { if (!(k in o)) o[k] = '' })
  SHIFT_EXTRA_FIELDS.forEach(([k, , t]) => { o[k] = t === 'number' ? '' : '' })
  o.machines = emptyMachines()
  return o
}

export default function LogShift() {
  const toast = useToast()
  const [form, setForm] = useState(empty())
  const [busy, setBusy] = useState(false)
  const [lastSaved, setLastSaved] = useState(null)   // { id, label } for the PDF link

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const setMachine = (code, attr, v) =>
    setForm(f => ({ ...f, machines: { ...f.machines, [code]: { ...f.machines[code], [attr]: v } } }))
  const warnings = shiftWarnings(form)

  const submit = async () => {
    if (!form.work_date) { toast.err('Pick a date first'); return }
    setBusy(true)
    const payload = { ...form }
    SHIFT_NUM_KEYS.forEach(k => { payload[k] = parseFloat(form[k]) || 0 })
    payload.sched_hours = parseFloat(form.sched_hours) || 8
    // Coerce the extra report fields: numbers to numbers, text left as-is.
    SHIFT_EXTRA_FIELDS.forEach(([k, , t]) => { if (t === 'number') payload[k] = parseFloat(form[k]) || 0 })
    // Normalise the per-machine grid (numeric attrs → numbers).
    payload.machines = {}
    SHIFT_MACHINES.forEach(({ code }) => {
      const src = form.machines?.[code] || {}
      const out = {}
      MACHINE_ATTRS.forEach(([attr]) => {
        out[attr] = NUM_ATTRS.has(attr) ? (parseFloat(src[attr]) || 0) : (src[attr] || '')
      })
      payload.machines[code] = out
    })
    try {
      const res = await api.createShift(payload)
      if (res && res[OFFLINE_QUEUED]) {
        toast.info(`Saved offline — ${payload.work_date} · ${payload.shift} shift will sync when reconnected.`)
        setLastSaved(null)
      } else {
        toast.ok(`Saved ${payload.work_date} · ${payload.shift} shift — synced to all dashboards.`)
        setLastSaved({ id: res.id, label: `${payload.work_date} · ${payload.shift}` })
      }
      setForm(empty())
    } catch (e) {
      toast.err(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="main">
      <PageHead title="Log a Production Shift" sub="End-of-shift figures · saves to the shared database" />
      <div className="card" style={{ maxWidth: 980 }}>
        <div className="banner">Entries are saved to the central database and appear instantly on every dashboard for the whole team.</div>

        <div className="form-section">Shift</div>
        <div className="form-grid">
          <div className="fld"><label>Date</label><input type="date" value={form.work_date} onChange={e => set('work_date', e.target.value)} /></div>
          <div className="fld"><label>Shift</label>
            <select value={form.shift} onChange={e => set('shift', e.target.value)}>
              <option>Day</option><option>Afternoon</option><option>Night</option>
            </select>
          </div>
        </div>

        {SHIFT_GROUPS.map(([section, fields]) => (
          <div key={section}>
            <div className="form-section">{section}</div>
            <div className="form-grid">
              {fields.map(([k, lbl]) => (
                <div className="fld" key={k}>
                  <label>{lbl}</label>
                  <input type="number" value={form[k]} placeholder="0" onChange={e => set(k, e.target.value)} />
                </div>
              ))}
            </div>
          </div>
        ))}

        <div className="form-section">Machine Detail (for the shift report)</div>
        <div className="tgt-wrap">
          <table className="tgt-grid">
            <thead>
              <tr>
                <th>Machine</th>
                {MACHINE_ATTRS.map(([k, lbl]) => <th key={k}>{lbl}</th>)}
              </tr>
            </thead>
            <tbody>
              {SHIFT_MACHINES.map(({ code, label }) => (
                <tr key={code}>
                  <td className="tgt-metric">{label}</td>
                  {MACHINE_ATTRS.map(([attr, , type]) => (
                    <td key={attr}>
                      <input type={type === 'number' ? 'number' : 'text'}
                        value={form.machines?.[code]?.[attr] ?? ''}
                        placeholder={type === 'number' ? '0' : '—'}
                        onChange={e => setMachine(code, attr, e.target.value)} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="hint" style={{ marginTop: 8 }}>Quantities come from the Output &amp; Hot Press figures above; this grid adds the hours, rates, operators and product detail for the shift report.</div>

        <div className="form-section">Shift Details &amp; Notes</div>
        <div className="form-grid">
          {SHIFT_EXTRA_FIELDS.map(([k, lbl, type]) => (
            <div className={`fld ${type === 'textarea' ? 'full' : ''}`} key={k}>
              <label>{lbl}</label>
              {type === 'textarea'
                ? <textarea value={form[k]} placeholder="—" onChange={e => set(k, e.target.value)} />
                : <input type={type === 'number' ? 'number' : 'text'} value={form[k]} placeholder={type === 'number' ? '0' : '—'} onChange={e => set(k, e.target.value)} />}
            </div>
          ))}
          <div className="fld full"><label>Comments</label>
            <textarea value={form.comment} placeholder="e.g. 30mins — washing of molds; fuel opening 6,900L / closing 6,300L…" onChange={e => set('comment', e.target.value)} />
          </div>
        </div>

        {warnings.length > 0 && (
          <div className="entry-warn">
            {warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
          </div>
        )}

        <div className="form-actions">
          <button className="btn btn-primary" onClick={submit} disabled={busy}>{busy ? 'Saving…' : 'Save Shift'}</button>
          <button className="btn btn-ghost" onClick={() => { setForm(empty()); setLastSaved(null) }}>Clear</button>
          {lastSaved && (
            <button className="btn btn-ghost" onClick={() => api.downloadShiftReport(lastSaved.id).catch(e => toast.err(e.message))}>
              ⤓ Shift report PDF ({lastSaved.label})
            </button>
          )}
          <span className="hint">The shift report is also emailed automatically at shift end when enabled.</span>
        </div>
      </div>
    </div>
  )
}
