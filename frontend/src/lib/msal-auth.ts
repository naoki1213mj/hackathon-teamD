/**
 * MSAL.js 認証。Voice Live 用のユーザー委任トークンを取得する。
 *
 * Voice Live WebSocket はユーザー委任 AAD トークンが必要（MI トークンは 1006 で拒否される）。
 * ブラウザ上で MSAL.js を使い、Entra ID でユーザー認証してトークンを取得する。
 */

import { PublicClientApplication, type SilentRequest } from '@azure/msal-browser'

let msalInstance: PublicClientApplication | null = null

export interface MsalConfig {
  clientId: string
  tenantId: string
}

const SCOPES = ['https://cognitiveservices.azure.com/.default']

export async function initMsal(config: MsalConfig): Promise<void> {
  if (msalInstance) return

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
  await msalInstance.handleRedirectPromise()
}

export async function getVoiceLiveToken(config: MsalConfig): Promise<string | null> {
  if (!msalInstance) {
    await initMsal(config)
  }
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
    } catch {
      // サイレント取得失敗 → ポップアップにフォールバック
    }
  }

  try {
    const response = await msalInstance.acquireTokenPopup({
      scopes: SCOPES,
    })
    return response.accessToken
  } catch (err) {
    console.warn('MSAL token acquisition failed:', err)
    return null
  }
}
