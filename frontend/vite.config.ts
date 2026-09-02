import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const backend = 'http://qdata-backend:8000'

const proxyTarget = {
  target: backend,
  changeOrigin: true,
  configure: (proxy: any) => {
    proxy.on('error', (err: any, _req: any, res: any) => {
      console.error('[vite proxy error]', err.message)
      if (res?.writeHead) {
        try { res.writeHead(502); res.end('Bad Gateway') } catch {}
      }
    })
  },
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/auth': proxyTarget,
      '/analyze': proxyTarget,
      '/reports': proxyTarget,
      '/rules': proxyTarget,
      '/synthetic': proxyTarget,
      '/scheduler': proxyTarget,
      '/upload': proxyTarget,
      '/processes': proxyTarget,
      '/datasources': proxyTarget,
      '/sources': proxyTarget,
      '/api': proxyTarget,
      '/admin': proxyTarget,
      '/health': proxyTarget,
    },
  },
})
