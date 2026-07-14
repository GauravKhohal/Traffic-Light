import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev (vite on :5173) proxy API + WebSocket to the FastAPI backend on :8000.
// In production the backend serves the built files, so same-origin needs no proxy.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
