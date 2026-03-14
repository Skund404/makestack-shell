import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      // Module frontend bundles — resolved at build time when modules are installed.
      // Each key maps to the module's frontend/ directory via its package_path.
      '@kitchen-frontend': path.resolve(__dirname, '../../makestack-addons/modules/kitchen/frontend'),
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:3000',
      '/modules': 'http://localhost:3000',
    },
  },
})
