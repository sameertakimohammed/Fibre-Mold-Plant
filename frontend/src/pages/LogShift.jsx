import { useState } from 'react'
import { api, OFFLINE_QUEUED } from '../api/client'
import { PageHead } from '../components/ui'
import { SHIFT_GROUPS, SHIFT_NUM_KEYS } from '../components/shiftFields'
import { useToast } from '../context/ToastContext'
import { shiftWarnings } from '../lib/validate'

const empty = () => {
  const o = { work_date: '', shift: 'Day', comment: '', sched_hours: 8 }
  SHIFT_NUM_KEYS.forEach(k => { if (!(k in o)) o[k] = '' })
  return o
}

export default function LogShift() {
  const toast = useToast()
  const [form, setForm] = useState(empty())
  const [busy, setBusy] = useState(false)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const warnings = shiftWarnings(form)

  const submit = async () => {
    if (!form.work_date) { toast.err('Pick a date first'); return }
    setBusy(true)
    const payload = { ...form }
    SHIFT_NUM_KEYS.forEach(k => { payload[k] = parseFloat(form[k]) || 0 })
    payload.sched_hours = parseFloat(form.sched_hours) || 8
    try {
      const res = await api.createShift(payload)
      if (res && res[OFFLINE_QUEUED]) {
        toast.info(`Saved offline — ${payload.work_date} · ${payload.shift} shift will sync when reconnected.`)
      } else {
        toast.ok(`Saved ${payload.work_date} · ${payload.shift} shift — synced to all dashboards.`)
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

        <div className="form-section">Notes</div>
        <div className="form-grid">
          <div className="fld full"><label>Comments</label>
            <textarea value={form.comment} placeholder="e.g. 30mins — washing of molds, removing products…" onChange={e => set('comment', e.target.value)} />
          </div>
        </div>

        {warnings.length > 0 && (
          <div className="entry-warn">
            {warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
          </div>
        )}

        <div className="form-actions">
          <button className="btn btn-primary" onClick={submit} disabled={busy}>{busy ? 'Saving…' : 'Save Shift'}</button>
          <button className="btn btn-ghost" onClick={() => setForm(empty())}>Clear</button>
          <span className="hint">Cleaning, mold, and other minutes also drive the downtime cause breakdown.</span>
        </div>
      </div>
    </div>
  )
}
