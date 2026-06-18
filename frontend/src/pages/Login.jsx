import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [username, setU] = useState('')
  const [password, setP] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      const me = await login(username, password)
      nav(me.must_change_password ? '/account' : '/')
    } catch (e) {
      setErr(e.message || 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="lc-brand">
          <div className="logo">G</div>
          <div>
            <h2>Fibre Mold Plant</h2>
          </div>
        </div>
        <div className="lc-tag">Golden Manufacturers · Recycling Department</div>
        <div className="fld">
          <label>Username</label>
          <input value={username} onChange={e => setU(e.target.value)} autoFocus autoComplete="username" />
        </div>
        <div className="fld">
          <label>Password</label>
          <input type="password" value={password} onChange={e => setP(e.target.value)} autoComplete="current-password" />
        </div>
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        {err && <div className="err">{err}</div>}
        <div className="login-hint">Plant operations dashboard · authorised users only</div>
      </form>
    </div>
  )
}
