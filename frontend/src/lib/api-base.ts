/**
 * SPA の base prefix を考慮した URL を組み立てる。
 *
 * Vite の `base` 設定により、production build では `/app/` が、
 * dev build では `/` が `import.meta.env.BASE_URL` として注入される。
 * APIM 経由の本番 URL `https://<apim>/app/api/...` でも、CA 直 URL
 * (deprecated) や localhost dev でも同じ呼び出しコードで動くようにする。
 *
 * 例:
 *   apiUrl('/api/chat') → '/api/chat' (dev) / '/app/api/chat' (prod)
 *   apiUrl('api/chat')  → '/api/chat' (dev) / '/app/api/chat' (prod)
 *   apiUrl('/auth-redirect.html') → '/app/auth-redirect.html' (prod)
 */
export function apiUrl(path: string): string {
  const base = import.meta.env.BASE_URL || '/'
  const normalized = path.startsWith('/') ? path.slice(1) : path
  return base + normalized
}
