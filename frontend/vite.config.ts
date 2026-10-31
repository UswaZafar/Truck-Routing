/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  build: {
    // maplibre-gl (~1 MB) is its own lazily loaded chunk; the app shell stays small.
    chunkSizeWarningLimit: 1200,
  },
  server: {
    // The Django API runs on :8000 in development; same origin in production.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
