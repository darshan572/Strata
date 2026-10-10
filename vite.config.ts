import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/search': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/suggest': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/crawl': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/crawl-seeds': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/crawl-queue': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/frontier': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/pagerank': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/graph': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/reload-index': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/debug': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
