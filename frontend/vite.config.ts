import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'
import os from 'os'

// Get the host's network interfaces
const getHostIp = () => {
  const interfaces = os.networkInterfaces();
  for (const iface of Object.values(interfaces)) {
    if (!iface) continue;
    for (const alias of iface) {
      if (alias.family === 'IPv4' && !alias.internal) {
        return alias.address;
      }
    }
  }
  return 'localhost';
};

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
        target: isProd ? 'https://api.pcapserver.com' : 'https://localhost:3000',
        changeOrigin: true,
        secure: isProd,
      },
    },
    port: 5173,
    host: '0.0.0.0',
    strictPort: true,
    hmr: !isProd ? {
      protocol: 'wss',
      host: getHostIp(),
      clientPort: 5173
    } : undefined
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
