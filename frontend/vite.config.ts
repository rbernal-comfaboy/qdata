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

// SPA deep links collide with API proxy prefixes (e.g. /processes/{id}).
// A browser navigation (refresh) sends Accept: text/html and carries NO token,
// so it must fall back to index.html instead of hitting the FastAPI backend.
const spaFallbackBeforeProxy = {
  name: 'qdata-spa-fallback-before-proxy',
  configureServer(server: any) {
    server.middlewares.use((req: any, _res: any, next: any) => {
      const accept = (req.headers.accept || '') as string
      const path = (req.url || '').split('?')[0]
      if (
        accept.includes('text/html') &&
        /^\/(processes|analyze|reports|rules|scheduler|datasources|admin)(\/|$)/.test(path)
      ) {
        req.url = '/'
      }
      next()
    })
  },
}

export default defineConfig({
  plugins: [react(), tailwindcss(), spaFallbackBeforeProxy],
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
