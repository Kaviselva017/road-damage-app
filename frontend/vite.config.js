import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { sentryVitePlugin } from "@sentry/vite-plugin"

export default defineConfig({
  plugins: [
    react(),
    // Sentry plugin must be after react plugin
    process.env.SENTRY_AUTH_TOKEN ? sentryVitePlugin({
      org: process.env.SENTRY_ORG,
      project: process.env.SENTRY_PROJECT,
      authToken: process.env.SENTRY_AUTH_TOKEN,
      sourcemaps: { assets: './dist/**' },
      release: { name: 'roadwatch-dashboard@2.2.0' },
    }) : null,
  ],
  build: {
    sourcemap: true, // Required for Sentry to map errors to original source code
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-maps': ['react-leaflet', 'leaflet'],
          'vendor-charts': ['recharts'],
          'vendor-firebase': ['firebase/app', 'firebase/auth'],
          'vendor-supabase': ['@supabase/supabase-js'],
        },
      },
    },
  },
})