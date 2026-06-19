import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// Apply the saved theme before first paint (avoids a flash of the wrong theme).
// Default to dark; honour the OS preference only when the user hasn't chosen.
const savedTheme = localStorage.getItem('fmp_theme')
  || (window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
document.documentElement.setAttribute('data-theme', savedTheme)
// NOTE: Chart.js is intentionally NOT imported here. It registers itself via
// src/api/charts.js, which every chart page imports. Because those pages are
// React.lazy()-loaded, the charts chunk only downloads when a chart page is
// first opened — keeping it out of the initial bundle for slow tablets.

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
