import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const backend = 'http://qdata-backend:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/auth': { target: backend, changeOrigin: true },
      '/analyze': { target: backend, changeOrigin: true },
      '/reports': { target: backend, changeOrigin: true },
      '/rules': { target: backend, changeOrigin: true },
      '/synthetic': { target: backend, changeOrigin: true },
      '/scheduler': { target: backend, changeOrigin: true },
      '/upload': { target: backend, changeOrigin: true },
      '/processes': { target: backend, changeOrigin: true },
      '/datasources': { target: backend, changeOrigin: true },
      '/sources': { target: backend, changeOrigin: true },
      '/api': { target: backend, changeOrigin: true },
      '/admin': { target: backend, changeOrigin: true },
      '/health': { target: backend, changeOrigin: true },
    },
  },
})
