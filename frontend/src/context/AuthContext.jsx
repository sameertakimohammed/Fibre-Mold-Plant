import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { api, setToken, getToken } from '../api/client'

const AuthCtx = createContext(null)

const RANK = { operator: 1, supervisor: 2, manager: 3, admin: 4 }

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!getToken()) { setLoading(false); return }
    api.me().then(setUser).catch(() => setToken(null)).finally(() => setLoading(false))
  }, [])

  // Sliding session: while logged in, periodically swap the still-valid token
  // for a fresh one so a long (12h) shift never gets logged out mid-entry. A
  // failed refresh is ignored — the token is still valid until it expires, and
  // the 401 handler in client.js redirects to login if it ever isn't.
  useEffect(() => {
    if (!user) return
    const REFRESH_MS = 6 * 60 * 60 * 1000  // 6h, well inside the 12h token life
    const id = setInterval(() => {
      api.refresh().then(r => setToken(r.access_token)).catch(() => {})
    }, REFRESH_MS)
    return () => clearInterval(id)
  }, [user])

  const login = useCallback(async (username, password) => {
    const res = await api.login(username, password)
    setToken(res.access_token)
    const me = await api.me()
    setUser(me)
    return me
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  const can = useCallback((minRole) => {
    if (!user) return false
    return RANK[user.role] >= RANK[minRole]
  }, [user])

  return (
    <AuthCtx.Provider value={{ user, setUser, loading, login, logout, can }}>
      {children}
    </AuthCtx.Provider>
  )
}

export const useAuth = () => useContext(AuthCtx)
