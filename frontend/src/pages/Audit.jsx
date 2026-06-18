import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import { PageHead } from '../components/ui'
import { useToast } from '../context/ToastContext'

const PAGE = 50

function fmtTime(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  if (isNaN(d)) return ts
  return d.toLocaleString()
}

function shortId(id) {
  if (!id) return '—'
  const s = String(id)
  return s.length > 8 ? s.slice(0, 8) : s
}

// Render the changes payload as "field: old → new" rows when possible,
// otherwise fall back to a pretty-printed JSON block.
function Changes({ changes }) {
  if (changes == null) return <span style={{ color: 'var(--dim)' }}>—</span>

  let obj = changes
  if (typeof changes === 'string') {
    try { obj = JSON.parse(changes) } catch { return <pre style={preStyle}>{changes}</pre> }
  }

  if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
    const entries = Object.entries(obj)
    const allDiffs = entries.every(([, v]) => v && typeof v === 'object' && ('old' in v || 'new' in v))
    if (entries.length && allDiffs) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {entries.map(([field, v]) => (
            <div key={field} style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>
              <span style={{ color: 'var(--amber)' }}>{field}</span>{': '}
              <span style={{ color: 'var(--red)' }}>{JSON.stringify(v.old)}</span>
              {' → '}
              <span style={{ color: 'var(--green)' }}>{JSON.stringify(v.new)}</span>
            </div>
          ))}
        </div>
      )
    }
  }

  return <pre style={preStyle}>{JSON.stringify(obj, null, 2)}</pre>
}

const preStyle = {
  fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--mut)',
  whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0,
  maxHeight: 220, overflow: 'auto',
}

export default function Audit() {
  const toast = useToast()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [offset, setOffset] = useState(0)
  const [expanded, setExpanded] = useState(null)
  const [verify, setVerify] = useState(null)
  const [verifying, setVerifying] = useState(false)
  const [filters, setFilters] = useState({ action: '', entity_type: '', actor: '' })

  const load = useCallback(() => {
    setLoading(true)
    api.listAudit({ ...filters, limit: PAGE, offset })
      .then(data => setRows(Array.isArray(data) ? data : (data?.items || [])))
      .catch(e => toast.err(e.message))
      .finally(() => setLoading(false))
  }, [filters, offset])

  useEffect(() => { load() }, [load])

  const applyFilters = (e) => { e.preventDefault(); setOffset(0); load() }
  const clearFilters = () => { setFilters({ action: '', entity_type: '', actor: '' }); setOffset(0) }

  const runVerify = async () => {
    setVerifying(true)
    try {
      const r = await api.verifyAudit()
      setVerify(r)
    } catch (e) {
      setVerify({ ok: false, reason: e.message })
    } finally {
      setVerifying(false)
    }
  }

  const verifyBtn = (
    <button className="btn btn-primary" onClick={runVerify} disabled={verifying}>
      {verifying ? 'Verifying…' : '🔒 Verify integrity'}
    </button>
  )

  const f = filters

  return (
    <div className="main">
      <PageHead title="Audit Trail" sub="Tamper-evident record of every change" right={verifyBtn} />

      {verify && (
        <div
          className="banner"
          style={verify.ok
            ? { background: 'rgba(63,185,80,.12)', borderColor: 'rgba(63,185,80,.3)', color: 'var(--green)' }
            : { background: 'rgba(240,85,109,.12)', borderColor: 'rgba(240,85,109,.3)', color: 'var(--red)' }}
        >
          {verify.ok
            ? `✓ Chain intact — ${verify.checked ?? 0} rows checked.`
            : `✕ BROKEN${verify.broken_at_id != null ? ` at id ${verify.broken_at_id}` : ''}: ${verify.reason || 'integrity check failed'}`}
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <form className="form-grid" onSubmit={applyFilters} style={{ alignItems: 'end' }}>
          <div className="fld">
            <label>Action</label>
            <input value={f.action} placeholder="e.g. update, delete"
              onChange={e => setFilters(p => ({ ...p, action: e.target.value }))} />
          </div>
          <div className="fld">
            <label>Entity type</label>
            <input value={f.entity_type} placeholder="e.g. shift, user"
              onChange={e => setFilters(p => ({ ...p, entity_type: e.target.value }))} />
          </div>
          <div className="fld">
            <label>Actor</label>
            <input value={f.actor} placeholder="username"
              onChange={e => setFilters(p => ({ ...p, actor: e.target.value }))} />
          </div>
          <div className="fld" style={{ display: 'flex', gap: 8, alignItems: 'end' }}>
            <button type="submit" className="btn btn-primary">Filter</button>
            <button type="button" className="btn btn-ghost" onClick={clearFilters}>Clear</button>
          </div>
        </form>
      </div>

      <div className="card">
        <div className="tbl-scroll" style={{ maxHeight: 560 }}>
          <table>
            <thead>
              <tr>
                <th>Time</th><th>Actor</th><th>Action</th><th>Entity</th><th>Request</th><th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => {
                const open = expanded === r.id
                return [
                  <tr key={r.id}>
                    <td style={{ textAlign: 'left', whiteSpace: 'nowrap', fontFamily: 'var(--mono)', fontSize: 12 }}>{fmtTime(r.created_at || r.at || r.timestamp)}</td>
                    <td style={{ textAlign: 'left' }}>{r.actor_username || r.actor || '—'}</td>
                    <td style={{ textAlign: 'left' }}><span className="tag">{r.action || '—'}</span></td>
                    <td style={{ textAlign: 'left', fontFamily: 'var(--mono)', fontSize: 12 }}>
                      {r.entity_type || '—'}{r.entity_id != null ? `#${r.entity_id}` : ''}
                    </td>
                    <td style={{ textAlign: 'left', fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--dim)' }}>{shortId(r.request_id)}</td>
                    <td style={{ textAlign: 'right' }}>
                      <button className="btn btn-ghost btn-sm" onClick={() => setExpanded(open ? null : r.id)}>
                        {open ? 'Hide' : 'Details'}
                      </button>
                    </td>
                  </tr>,
                  open && (
                    <tr key={`${r.id}-d`}>
                      <td colSpan={6} style={{ textAlign: 'left', background: 'var(--bg2)' }}>
                        <div style={{ padding: '6px 2px' }}>
                          <div className="csub" style={{ margin: '0 0 8px' }}>Changes</div>
                          <Changes changes={r.changes ?? r.diff ?? r.payload} />
                        </div>
                      </td>
                    </tr>
                  ),
                ]
              })}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={6} style={{ color: 'var(--dim)', textAlign: 'left' }}>No audit events match these filters.</td></tr>
              )}
              {loading && (
                <tr><td colSpan={6} style={{ color: 'var(--dim)', textAlign: 'left' }}>Loading…</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="form-actions" style={{ marginTop: 14, justifyContent: 'space-between' }}>
          <span className="hint">Showing {rows.length ? offset + 1 : 0}–{offset + rows.length}</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-ghost btn-sm" disabled={offset === 0 || loading}
              onClick={() => setOffset(o => Math.max(0, o - PAGE))}>Prev</button>
            <button className="btn btn-ghost btn-sm" disabled={rows.length < PAGE || loading}
              onClick={() => setOffset(o => o + PAGE)}>Next</button>
          </div>
        </div>
      </div>
    </div>
  )
}
