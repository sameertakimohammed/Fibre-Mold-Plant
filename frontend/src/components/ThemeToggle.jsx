import { useState } from 'react'

// Light/dark theme switch. The initial theme is applied in main.jsx before
// first paint; this button flips <html data-theme> and persists the choice.
export default function ThemeToggle() {
  const [theme, setTheme] = useState(
    () => document.documentElement.getAttribute('data-theme') || 'dark'
  )
  const toggle = () => {
    // Read the live attribute (not React state) so the switch is correct even
    // on rapid clicks before a re-render.
    const cur = document.documentElement.getAttribute('data-theme') || 'dark'
    const next = cur === 'dark' ? 'light' : 'dark'
    document.documentElement.setAttribute('data-theme', next)
    localStorage.setItem('fmp_theme', next)
    setTheme(next)
  }
  return (
    <button
      className="theme-toggle"
      onClick={toggle}
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
    >
      {theme === 'dark' ? '☀' : '☾'}
    </button>
  )
}
