import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'node:path'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'Akıllı Sıcak Satış Yönetim Sistemi',
        short_name: 'Van Sales',
        description: 'Sıcak satış / van sales saha yönetim uygulaması',
        theme_color: '#0f172a',
        background_color: '#f8fafc',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        lang: 'tr',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        navigateFallbackDenylist: [/^\/api/, /^\/docs/, /^\/openapi/],
        runtimeCaching: [
          {
            // Reference data the field app must still show with no signal.
            urlPattern: /\/api\/v1\/(products|customers|campaigns)(\?.*)?$/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'vs-reference',
              expiration: { maxEntries: 300, maxAgeSeconds: 60 * 60 * 24 },
            },
          },
          {
            urlPattern: /\/api\/v1\/system\/i18n\//,
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'vs-i18n' },
          },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        // Vite 8 (Rolldown) no longer accepts the object form of manualChunks;
        // the function form keeps the same react/charts/map chunk split.
        manualChunks(id: string) {
          if (!id.includes('node_modules')) return undefined
          if (/[\\/]node_modules[\\/](react|react-dom|scheduler|react-router|react-router-dom)[\\/]/.test(id)) {
            return 'react'
          }
          if (/[\\/]node_modules[\\/]recharts[\\/]/.test(id)) return 'charts'
          if (/[\\/]node_modules[\\/]leaflet[\\/]/.test(id)) return 'map'
          return undefined
        },
      },
    },
  },
})
