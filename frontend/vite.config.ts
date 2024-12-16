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

export default defineConfig({
  plugins: [react()],
  root: '.',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
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
    port: 5173,
    host: '0.0.0.0',
    strictPort: true,
    hmr: {
      protocol: 'wss',
      host: getHostIp(),
      clientPort: 5173
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  }
}) 
