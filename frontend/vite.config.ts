import { resolve } from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
//
// `base` は production build のとき `/app/` を採用する。これは APIM 経由で
// `https://<apim>.azure-api.net/app/...` で SPA を配信するため。dev build
// では `/` のままにして Vite dev server / proxy がそのまま動くようにする。
// `VITE_BASE_URL` 環境変数で override も可能 (CI で staging-only を切り替える等)。
export default defineConfig(({ mode }) => {
  const base = process.env.VITE_BASE_URL ?? (mode === 'production' ? '/app/' : '/')
  return {
    base,
    plugins: [react(), tailwindcss()],
    build: {
      rollupOptions: {
        input: {
          main: resolve(__dirname, 'index.html'),
          authRedirect: resolve(__dirname, 'auth-redirect.html'),
        },
      },
    },
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
