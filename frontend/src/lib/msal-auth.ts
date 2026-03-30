/**
 * MSAL.js 認証。Voice Live 用のユーザー委任トークンを取得する。
 *
 * Voice Live WebSocket はユーザー委任 AAD トークンが必要（MI トークンは 1006 で拒否される）。
 * ブラウザ上で MSAL.js を使い、Entra ID でユーザー認証してトークンを取得する。
 *
 * Edge の COOP (Cross-Origin-Opener-Policy) でポップアップがブロックされるため、
 * redirect 方式を使用する。
 */

import { PublicClientApplication, type SilentRequest, InteractionRequiredAuthError } from '@azure/msal-browser'

let msalInstance: PublicClientApplication | null = null
let initPromise: Promise<void> | null = null

export interface MsalConfig {
  clientId: string
  tenantId: string
}

const SCOPES = ['https://cognitiveservices.azure.com/user_impersonation']

export async function initMsal(config: MsalConfig): Promise<void> {
  if (msalInstance) return
  if (initPromise) { await initPromise; return }

  initPromise = (async () => {
    msalInstance = new PublicClientApplication({
      auth: {
        clientId: config.clientId,
        authority: `https://login.microsoftonline.com/${config.tenantId}`,
        redirectUri: window.location.origin,
      },
      cache: {
        cacheLocation: 'sessionStorage',
      },
    })

    await msalInstance.initialize()
    // redirect からの戻りを処理
    await msalInstance.handleRedirectPromise()
  })()

  await initPromise
}

export async function getVoiceLiveToken(config: MsalConfig): Promise<string | null> {
  await initMsal(config)
  if (!msalInstance) return null

  const accounts = msalInstance.getAllAccounts()

  if (accounts.length > 0) {
    try {
      const request: SilentRequest = {
        scopes: SCOPES,
        account: accounts[0],
      }
      const response = await msalInstance.acquireTokenSilent(request)
      return response.accessToken
    } catch (err) {
      if (err instanceof InteractionRequiredAuthError) {
        // サイレント失敗 → redirect で再認証
        await msalInstance.acquireTokenRedirect({ scopes: SCOPES })
        return null // redirect するため、ここには戻らない
      }
      console.warn('MSAL silent token failed:', err)
    }
  }

  // 未ログイン → redirect でログイン
  try {
    await msalInstance.acquireTokenRedirect({ scopes: SCOPES })
    // redirect するため、ここには戻らない
    return null
  } catch (err) {
    console.warn('MSAL token acquisition failed:', err)
    return null
  }
}
