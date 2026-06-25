import { useState, lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ToastProvider } from './context/ToastContext'
import { PageSkeleton } from './components/ui'
import ErrorBoundary from './components/ErrorBoundary'
import SystemHealth from './components/SystemHealth'
import NotificationsBell from './components/NotificationsBell'
import SyncStatus from './components/SyncStatus'
import ThemeToggle from './components/ThemeToggle'
import Login from './pages/Login' // eager: entry point

// Lazy-loaded so operators on slow tablets don't download every page +
// all charts upfront. Each becomes its own chunk loaded on first visit.
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Production = lazy(() => import('./pages/Production'))
const Fuel = lazy(() => import('./pages/Fuel'))
const Downtime = lazy(() => import('./pages/Downtime'))
const Deliveries = lazy(() => import('./pages/Deliveries'))
const Materials = lazy(() => import('./pages/Materials'))
const Reports = lazy(() => import('./pages/Reports'))
const Targets = lazy(() => import('./pages/Targets'))
const LogShift = lazy(() => import('./pages/LogShift'))
const Account = lazy(() => import('./pages/Account'))
const Users = lazy(() => import('./pages/Users'))
const Audit = lazy(() => import('./pages/Audit'))

const NAV = [
  { sec: 'Analytics', items: [
    { to: '/', label: 'Overview', ic: '▣', end: true },
    { to: '/production', label: 'Production', ic: '▤' },
    { to: '/fuel', label: 'Fuel & Energy', ic: '◆' },
    { to: '/downtime', label: 'Downtime', ic: '▼' },
  ] },
  { sec: 'Operations', items: [
    { to: '/deliveries', label: 'Deliveries', ic: '➜' },
    { to: '/materials', label: 'Stock & Bales', ic: '▦' },
    { to: '/log', label: 'Log Shift', ic: '＋' },
  ] },
  { sec: 'Reports', items: [
    { to: '/reports', label: 'Reports', ic: '🖨' },
    { to: '/targets', label: 'Targets', ic: '◎' },
  ] },
]

function Sidebar({ open, onClose }) {
  const { user, logout } = useAuth()
  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="brand">
        <div className="logo">G</div>
        <div>
          <div className="bt">Fibre Mold Plant</div>
          <div className="bs">Golden Manufacturers</div>
        </div>
      </div>
      <nav className="nav" onClick={onClose}>
        {NAV.map(group => (
          <div key={group.sec}>
            <div className="nav-sec">{group.sec}</div>
            {group.items.map(n => (
              <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? 'on' : '')}>
                <span className="ic">{n.ic}</span>{n.label}
              </NavLink>
            ))}
          </div>
        ))}
        <div className="nav-sec">Settings</div>
        {user?.role === 'admin' && (
          <NavLink to="/users" className={({ isActive }) => (isActive ? 'on' : '')}>
            <span className="ic">◉</span>Team & Access
          </NavLink>
        )}
        {user?.role === 'admin' && (
          <NavLink to="/audit" className={({ isActive }) => (isActive ? 'on' : '')}>
            <span className="ic">▤</span>Audit Trail
          </NavLink>
        )}
        <NavLink to="/account" className={({ isActive }) => (isActive ? 'on' : '')}>
          <span className="ic">⚙</span>My Account
        </NavLink>
      </nav>
      <div className="userbox">
        <div className="un">{user?.full_name}</div>
        <div className="ur">{user?.role}</div>
        <button onClick={logout}>Sign out</button>
      </div>
    </aside>
  )
}

function Protected({ children }) {
  const { user, loading } = useAuth()
  const loc = useLocation()
  const [open, setOpen] = useState(false)
  if (loading) return <div className="loading">Loading…</div>
  if (!user) return <Navigate to="/login" state={{ from: loc }} replace />
  return (
    <div className="app">
      <div className={`scrim ${open ? 'show' : ''}`} onClick={() => setOpen(false)} />
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <div className="topbar">
          <button className="hamburger" onClick={() => setOpen(true)} aria-label="Menu">☰</button>
          <div>
            <div className="tb-title">Fibre Mold Plant</div>
            <div className="tb-sub">Golden Manufacturers</div>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
            <SyncStatus />
            <ThemeToggle />
            <NotificationsBell />
          </div>
        </div>
        <SystemHealth />
        <ErrorBoundary>
          <Suspense fallback={<PageSkeleton />}>
            {children}
          </Suspense>
        </ErrorBoundary>
      </div>
    </div>
  )
}

function AdminOnly({ children }) {
  const { user } = useAuth()
  if (user?.role !== 'admin') return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<Protected><Dashboard /></Protected>} />
            <Route path="/production" element={<Protected><Production /></Protected>} />
            <Route path="/fuel" element={<Protected><Fuel /></Protected>} />
            <Route path="/downtime" element={<Protected><Downtime /></Protected>} />
            <Route path="/deliveries" element={<Protected><Deliveries /></Protected>} />
            <Route path="/materials" element={<Protected><Materials /></Protected>} />
            <Route path="/reports" element={<Protected><Reports /></Protected>} />
            <Route path="/targets" element={<Protected><Targets /></Protected>} />
            <Route path="/log" element={<Protected><LogShift /></Protected>} />
            <Route path="/account" element={<Protected><Account /></Protected>} />
            <Route path="/users" element={<Protected><AdminOnly><Users /></AdminOnly></Protected>} />
            <Route path="/audit" element={<Protected><AdminOnly><Audit /></AdminOnly></Protected>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ToastProvider>
  )
}
