import { useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { PageHead } from '../components/ui'

const ROLE_DESC = {
  operator: 'Log shifts only',
  supervisor: 'Log shifts · edit recent records · manage deliveries, bales & fuel',
  manager: 'Full analytics & reports · read-only (no data entry)',
  admin: 'Full control including user management',
}

export default function Account() {
  const { user, setUser } = useAuth()
  const toast = useToast()
  const [cur, setCur] = useState('')
  const [nw, setNw] = useState('')
  const [busy, setBusy] = useState(false)

  const isAD = user?.auth_source === 'ad'

  const submit = async () => {
    setBusy(true)
    try {
      await api.changePassword(cur, nw)
      toast.ok('Password updated.')
      setCur(''); setNw('')
      if (user?.must_change_password) setUser({ ...user, must_change_password: false })
    } catch (e) {
      toast.err(e.message)
    } finally { setBusy(false) }
  }

  return (
    <div className="main">
      <PageHead title="My Account" sub={`${user?.full_name} · ${user?.role}`} />

      <div className="card" style={{ maxWidth: 460, marginBottom: 16 }}>
        <div className="form-section">Account Details</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <span style={{ color: 'var(--dim)', minWidth: 100 }}>Username</span>
            <span>{user?.username}</span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <span style={{ color: 'var(--dim)', minWidth: 100 }}>Full name</span>
            <span>{user?.full_name}</span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <span style={{ color: 'var(--dim)', minWidth: 100 }}>Role</span>
            <span><strong>{user?.role}</strong> — {ROLE_DESC[user?.role]}</span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <span style={{ color: 'var(--dim)', minWidth: 100 }}>Auth</span>
            <span>{isAD ? 'Active Directory (Windows login)' : 'Local account'}</span>
          </div>
        </div>
      </div>

      {user?.must_change_password && !isAD && (
        <div className="banner">Please set a new password to secure your account.</div>
      )}

      {isAD ? (
        <div className="card" style={{ maxWidth: 460 }}>
          <div className="form-section">Password</div>
          <p style={{ color: 'var(--dim)', fontSize: 14, margin: 0 }}>
            Your password is managed by Active Directory. To change it, use Windows (Ctrl+Alt+Del → Change a password) or contact IT.
          </p>
        </div>
      ) : (
        <div className="card" style={{ maxWidth: 460 }}>
          <div className="form-section">Change Password</div>
          <div className="fld" style={{ marginBottom: 14 }}>
            <label>Current password</label>
            <input type="password" value={cur} onChange={e => setCur(e.target.value)} />
          </div>
          <div className="fld" style={{ marginBottom: 14 }}>
            <label>New password (min 6 chars)</label>
            <input type="password" value={nw} onChange={e => setNw(e.target.value)} />
          </div>
          <button className="btn btn-primary" onClick={submit} disabled={busy || !cur || !nw}>
            {busy ? 'Saving…' : 'Update Password'}
          </button>
        </div>
      )}
    </div>
  )
}
