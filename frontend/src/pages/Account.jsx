import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { PageHead, Card } from '../components/ui'

const ROLE_DESC = {
  operator: 'Log shifts only',
  supervisor: 'Log shifts · edit recent records · manage deliveries, bales & fuel',
  manager: 'Full analytics & reports · read-only (no data entry)',
  admin: 'Full control including user management',
}

const fmtBytes = (n) => {
  if (!n) return '0 B'
  const u = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(u.length - 1, Math.floor(Math.log(n) / Math.log(1024)))
  return `${(n / 1024 ** i).toFixed(i ? 1 : 0)} ${u[i]}`
}
const fmtAge = (h) => {
  if (h == null) return '—'
  if (h < 1) return `${Math.round(h * 60)} min ago`
  if (h < 48) return `${Math.round(h)} h ago`
  return `${Math.round(h / 24)} days ago`
}

// Admin-only: latest database-backup status.
function BackupCard() {
  const [bk, setBk] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { api.adminBackups().then(setBk).catch(e => setErr(e.message)) }, [])

  return (
    <Card title="Database Backups" sub="Nightly pg_dump status (read-only view of the backup volume)">
      {err && <div className="err">{err}</div>}
      {!bk ? <div className="hint">Checking…</div> : !bk.configured ? (
        <div className="hint">No backup directory is mounted (expected on local/dev). On the plant PC the nightly backup sidecar fills it.</div>
      ) : bk.count === 0 ? (
        <div className="err">⚠ No backups found yet in {bk.dir}. Check that the db-backup container is running.</div>
      ) : (
        <div className="row-flex">
          <div className="mini"><div className="m-lbl">Latest backup</div><div className="m-val" style={{ fontSize: 15 }}>{fmtAge(bk.latest.age_hours)}</div></div>
          <div className="mini"><div className="m-lbl">Size</div><div className="m-val" style={{ fontSize: 15 }}>{fmtBytes(bk.latest.size_bytes)}</div></div>
          <div className="mini"><div className="m-lbl">Total dumps</div><div className="m-val" style={{ fontSize: 15 }}>{bk.count}</div></div>
          <div className="mini"><div className="m-lbl">Status</div>
            <div className="m-val" style={{ fontSize: 15, color: bk.stale ? 'var(--red)' : 'var(--green)' }}>
              {bk.stale ? '⚠ Stale' : '✓ Current'}
            </div>
          </div>
        </div>
      )}
      {bk?.latest && <div className="hint" style={{ marginTop: 10 }}>Most recent file: {bk.latest.name}</div>}
    </Card>
  )
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

      {user?.role === 'admin' && (
        <div style={{ maxWidth: 640, marginBottom: 16 }}><BackupCard /></div>
      )}

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
