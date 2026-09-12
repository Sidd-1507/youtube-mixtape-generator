import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Proxy /upload, /mixtape, /description, /video, /storage, /health
      // to the FastAPI backend during development.
      // This avoids CORS issues when fetching audio/video blobs.
      '/upload': 'http://localhost:8000',
      '/mixtape': 'http://localhost:8000',
      '/description': 'http://localhost:8000',
      '/video': 'http://localhost:8000',
      '/storage': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
