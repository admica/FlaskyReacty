import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'
import os from 'os'

// Environment detection
const isProd = process.env.NODE_ENV === 'production'
const hostname = os.hostname()
const isDev = process.env.NODE_ENV === 'development'

export default defineConfig({
  plugins: [react()],
  root: '.',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: !isProd,
  },
  server: {
    https: {
      key: fs.readFileSync('/opt/pcapserver/ssl/cert.key'),
      cert: fs.readFileSync('/opt/pcapserver/ssl/cert.crt'),
    },
    proxy: {
      '/api': {
        target: 'https://localhost:3000',
        changeOrigin: true,
        secure: false,
      },
    },
    host: true,
    port: 5173,
    strictPort: true,
    hmr: {
      protocol: 'wss',
      host: isDev ? 'localhost' : hostname,
      clientPort: 5173
    }
  },
  resolve: {
    alias: [
      { find: '@', replacement: path.resolve(__dirname, 'src') }
    ]
  }
})
