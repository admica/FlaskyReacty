import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'
import os from 'os'

// Determine if we're in production
const isProd = process.env.NODE_ENV === 'production';

export default defineConfig({
  plugins: [react()],
  root: '.',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: !isProd,
  },
  server: {
    https: !isProd ? {
      key: fs.readFileSync('/opt/pcapserver/ssl/cert.key'),
      cert: fs.readFileSync('/opt/pcapserver/ssl/cert.crt'),
    } : undefined,
    proxy: {
      '/api': {
        target: isProd ? 'https://api.pcapserver.com' : `https://${os.hostname()}:3000`,
        changeOrigin: true,
        secure: isProd,
      },
    },
    port: 5173,
    host: true,
    strictPort: true,
    hmr: {
      protocol: 'wss',
      clientPort: 5173,
      host: os.hostname()
    }
  },
  resolve: {
    alias: [
      {
        find: '@',
        replacement: path.resolve(__dirname, 'src')
      }
    ]
  }
}) 
