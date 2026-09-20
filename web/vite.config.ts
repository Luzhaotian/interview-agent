import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueJsx(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        timeout: 300000,
        proxyTimeout: 300000,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes, _req, res) => {
            const type = String(proxyRes.headers['content-type'] || '')
            if (!type.includes('text/event-stream')) return
            // 避免开发代理把 SSE 缓冲成一整段再吐给浏览器
            res.setHeader('Cache-Control', 'no-cache, no-transform')
            res.setHeader('X-Accel-Buffering', 'no')
            res.setHeader('Connection', 'keep-alive')
            if (typeof (res as { flushHeaders?: () => void }).flushHeaders === 'function') {
              ;(res as { flushHeaders: () => void }).flushHeaders()
            }
          })
        },
      },
    },
  },
})
