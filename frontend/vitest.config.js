import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Dedicated test config so the PWA/build plugins in vite.config.js don't run
// under the test runner. jsdom gives the component tests a DOM; setup.js wires
// up jest-dom matchers.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
    css: false,
    include: ['src/**/*.{test,spec}.{js,jsx}'],
  },
})
