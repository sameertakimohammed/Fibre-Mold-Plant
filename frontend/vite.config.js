import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    // PWA: precaches the built app shell so the SPA loads with no network,
    // letting operators reach the Log Shift form to hand-key data offline.
    // Registers the SW only in the production build (default behaviour); dev is
    // untouched so the workflow / HMR are not disrupted.
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icons/icon-192.png', 'icons/icon-512.png'],
      manifest: {
        name: 'Fibre Mold Plant',
        short_name: 'Fibre Mold',
        description: 'Fibre Mold Plant dashboard — Golden Manufacturers',
        theme_color: '#0d1014',
        background_color: '#0d1014',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // Precache the built app shell (JS/CSS/HTML/icons) for offline SPA load.
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        // SPA fallback: any navigation while offline serves index.html so the
        // client router can take over. Exclude /api so API calls are never
        // intercepted by the navigation fallback.
        navigateFallback: 'index.html',
        navigateFallbackDenylist: [/^\/api/],
        cleanupOutdatedCaches: true,
      },
    }),
  ],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        // Function form so React (incl. react/jsx-runtime) is reliably grouped
        // into `vendor` BEFORE chart libs are considered. If jsx-runtime leaks
        // into the charts chunk, App.jsx's JSX would statically import it and
        // pull charts into the initial load — defeating the lazy split.
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('react-chartjs-2') || id.includes('/chart.js/') || id.includes('\\chart.js\\')) {
            return 'charts'
          }
          if (id.includes('/react') || id.includes('\\react') || id.includes('scheduler')) {
            // react, react-dom, react-router-dom, react/jsx-runtime, scheduler
            return 'vendor'
          }
        },
      },
    },
  },
})
