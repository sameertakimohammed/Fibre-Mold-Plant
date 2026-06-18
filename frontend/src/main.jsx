import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
// NOTE: Chart.js is intentionally NOT imported here. It registers itself via
// src/api/charts.js, which every chart page imports. Because those pages are
// React.lazy()-loaded, the charts chunk only downloads when a chart page is
// first opened — keeping it out of the initial bundle for slow tablets.

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
