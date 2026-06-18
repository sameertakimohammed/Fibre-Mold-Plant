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
