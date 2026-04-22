/**
 * MSAL リダイレクト認証結果のブリッジ。
 *
 * auth-redirect.html で handleRedirectPromise が取得したアクセストークンを
 * sessionStorage 経由でメインアプリの initMsal に渡す。
 *
 * MSAL の内部 sessionStorage キャッシュは新しい PCA インスタンスでも読み取れるが、
 * acquireTokenSilent が InteractionRequiredAuthError を投げるエッジケース（特に
 * 新しいインスタンスを生成した直後）がある。このブリッジはその場合でも認証コード
 * 交換で得た直接トークンを確実にメインアプリへ届ける。
 */

export const REDIRECT_BRIDGE_KEY = 'workIqMsalRedirectBridge'

/** ブリッジ経由で渡すリダイレクト結果 */
export interface RedirectBridgeResult {
  accessToken: string
  scopes: string[]
  /** トークン有効期限 (Unix ms) */
  expiresAt: number
}

/** ブリッジ結果を sessionStorage に書き込む（auth-redirect.html から呼ぶ） */
export function writeRedirectBridgeResult(result: RedirectBridgeResult): void {
  try {
    window.sessionStorage.setItem(REDIRECT_BRIDGE_KEY, JSON.stringify(result))
  } catch {
    // no-op
  }
}

/**
 * ブリッジ結果を sessionStorage から読み取って削除する（initMsal から呼ぶ）。
 * 期限切れや不正なエントリは null を返す。
 */
export function readAndClearRedirectBridgeResult(): RedirectBridgeResult | null {
  try {
    const raw = window.sessionStorage.getItem(REDIRECT_BRIDGE_KEY)
    if (!raw) return null
    window.sessionStorage.removeItem(REDIRECT_BRIDGE_KEY)

    const parsed = JSON.parse(raw) as Partial<RedirectBridgeResult>
    const accessToken = typeof parsed.accessToken === 'string' ? parsed.accessToken.trim() : ''
    const scopes = Array.isArray(parsed.scopes)
      ? parsed.scopes.filter((s): s is string => typeof s === 'string' && s.length > 0)
      : []
    const expiresAt = typeof parsed.expiresAt === 'number' ? parsed.expiresAt : 0

    if (!accessToken || scopes.length === 0 || expiresAt <= Date.now()) return null

    return { accessToken, scopes, expiresAt }
  } catch {
    return null
  }
}
