import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'

// Only disable SSL verification in development
if (process.env.NODE_ENV !== 'production') {
  process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0'
}

export default defineConfig({
  plugins: [react()],
  root: '.',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    https: process.env.NODE_ENV !== 'production' ? {
      key: fs.readFileSync('/opt/pcapserver/ssl/cert.key'),
      cert: fs.readFileSync('/opt/pcapserver/ssl/cert.crt'),
    } : false,
    proxy: {
      '/api/v1': {
        target: 'https://localhost:3000',
        changeOrigin: true,
        secure: false
      },
    },
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    hmr: {
      protocol: 'wss',
      host: '0.0.0.0',
      clientPort: 5173
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  }
})
