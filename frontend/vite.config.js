import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(async ({ mode }) => {
  // `npm run dev:phone` serves the app over HTTPS on your network, with the API reached through
  // /api (see .env.phone). Phones only give web pages the compass and camera on secure pages.
  if (mode !== 'phone') return { plugins: [react()], build: { chunkSizeWarningLimit: 2200 } }

  const { default: basicSsl } = await import('@vitejs/plugin-basic-ssl')
  return {
    plugins: [react(), basicSsl()],
    server: {
      host: true,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  }
})
