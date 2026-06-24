import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { PageHead } from '../components/ui'
import { useToast } from '../context/ToastContext'

const ROLES = ['operator', 'supervisor', 'manager', 'admin']

// Humanize a timestamp into a short "Xh ago" / date; 'never' when null.
function humanLogin(ts) {
  if (!ts) return 'never'
  const d = new Date(ts)
  if (isNaN(d)) return 'never'
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  if (diff < 7 * 86400) return `${Math.floor(diff / 86400)}d ago`
  return d.toLocaleDateString()
}

const isLocked = (u) => u.locked_until && new Date(u.locked_until).getTime() > Date.now()

export default function Users() {
  const toast = useToast()
  const [users, setUsers] = useState([])
  const [form, setForm] = useState({ username: '', full_name: '', password: '', role: 'operator' })
  const [busy, setBusy] = useState(false)

  const load = () => api.listUsers().then(setUsers).catch(e => toast.err(e.message))
  useEffect(() => { load() }, [])

  const create = async () => {
    setBusy(true)
    try {
      await api.createUser(form)
      toast.ok(`Created ${form.username}. Temporary password set — they'll be asked to change it.`)
      setForm({ username: '', full_name: '', password: '', role: 'operator' })
      load()
    } catch (e) { toast.err(e.message) } finally { setBusy(false) }
  }

  const changeRole = async (u, role) => { try { await api.updateUser(u.id, { role }); toast.ok(`${u.username} is now ${role}.`); load() } catch (e) { toast.err(e.message) } }
  const toggleActive = async (u) => { try { await api.updateUser(u.id, { is_active: !u.is_active }); load() } catch (e) { toast.err(e.message) } }
  // Local password reset: admin sets a new temporary password. The backend
  // forces must_change_password and revokes the user's existing tokens, so they
  // pick a new one at next login. AD accounts authenticate against Active
  // Directory, so a local reset wouldn't change their login — hide it for them.
  const resetPassword = async (u) => {
    const pw = prompt(`Set a new temporary password for ${u.username}.\nThey'll be required to change it at next login. Minimum 8 characters.`)
    if (pw === null) return // cancelled
    if (pw.length < 8) { toast.err('Password must be at least 8 characters.'); return }
    try { await api.updateUser(u.id, { password: pw }); toast.ok(`Password reset for ${u.username}. They'll set a new one at next login.`); load() } catch (e) { toast.err(e.message) }
  }
  const remove = async (u) => {
    if (!confirm(`Delete user ${u.username}? This cannot be undone.`)) return
    try { await api.deleteUser(u.id); toast.ok(`Deleted ${u.username}.`); load() } catch (e) { toast.err(e.message) }
  }

  return (
    <div className="main">
      <PageHead title="Team & Access" sub="Manage who can log shifts and view reports" />

      <div className="card" style={{ marginBottom: 18, maxWidth: 980 }}>
        <div className="form-section">Add Team Member</div>
        <div className="form-grid">
          <div className="fld"><label>Username</label><input value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))} /></div>
          <div className="fld"><label>Full name</label><input value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))} /></div>
          <div className="fld"><label>Temporary password</label><input value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} /></div>
          <div className="fld"><label>Role</label>
            <select value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
              {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        </div>
        <div className="form-actions">
          <button className="btn btn-primary" onClick={create} disabled={busy || !form.username || !form.full_name || !form.password}>Create User</button>
          <span className="hint">operator: log shifts only · supervisor: + deliveries/bales/fuel · manager: read-only analytics · admin: full control</span>
        </div>
        <p style={{ fontSize: 12, color: 'var(--dim)', marginTop: 8 }}>
          If Active Directory is enabled, staff can also log in with their Windows username — they are provisioned automatically on first login with the operator role.
        </p>
      </div>

      <div className="card">
        <div className="tbl-scroll">
          <table>
            <thead><tr><th>Username</th><th>Name</th><th>Role</th><th>Auth</th><th>Last login</th><th>Status</th><th style={{ textAlign: 'right' }}>Actions</th></tr></thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id}>
                  <td>{u.username}</td>
                  <td style={{ textAlign: 'left' }}>{u.full_name}</td>
                  <td>
                    <select value={u.role} onChange={e => changeRole(u, e.target.value)}
                      style={{ background: 'var(--bg)', border: '1px solid var(--line)', color: 'var(--ink)', borderRadius: 6, padding: '4px 8px', fontFamily: 'var(--mono)', fontSize: 12 }}>
                      {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td><span className={`tag ${u.auth_source === 'ad' ? 'r-supervisor' : ''}`}>{u.auth_source === 'ad' ? 'AD' : 'local'}</span></td>
                  <td style={{ textAlign: 'left', fontFamily: 'var(--mono)', fontSize: 12, color: u.last_login_at ? 'var(--mut)' : 'var(--dim)', whiteSpace: 'nowrap' }}>
                    {humanLogin(u.last_login_at)}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <span className={`tag ${u.is_active ? 'r-manager' : 'r-admin'}`}>{u.is_active ? 'active' : 'disabled'}</span>
                    {isLocked(u) && <span className="tag r-admin" style={{ marginLeft: 6 }}>locked</span>}
                    {u.failed_login_count > 0 && (
                      <span className="tag" style={{ marginLeft: 6, background: 'rgba(245,166,35,.15)', color: 'var(--amber)' }}>
                        {u.failed_login_count} fails
                      </span>
                    )}
                  </td>
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                    {u.auth_source !== 'ad' && (
                      <button className="btn btn-ghost btn-sm" onClick={() => resetPassword(u)} style={{ marginRight: 6 }}>Reset password</button>
                    )}
                    <button className="btn btn-ghost btn-sm" onClick={() => toggleActive(u)} style={{ marginRight: 6 }}>{u.is_active ? 'Disable' : 'Enable'}</button>
                    <button className="btn btn-danger btn-sm" onClick={() => remove(u)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
