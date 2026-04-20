import { getWorkIqGraphAuth, type DelegatedAuthStatus, type MsalConfig } from './msal-auth'

let cachedMsalConfigPromise: Promise<MsalConfig | null> | null = null

function normalizeMsalConfig(raw: unknown): MsalConfig | null {
  if (!raw || typeof raw !== 'object') return null
  const clientId = typeof (raw as { client_id?: unknown }).client_id === 'string'
    ? (raw as { client_id: string }).client_id.trim()
    : ''
  const tenantId = typeof (raw as { tenant_id?: unknown }).tenant_id === 'string'
    ? (raw as { tenant_id: string }).tenant_id.trim()
    : ''
  if (!clientId || !tenantId) return null
  return { clientId, tenantId }
}

async function getMsalConfig(): Promise<MsalConfig | null> {
  if (!cachedMsalConfigPromise) {
    cachedMsalConfigPromise = (async () => {
      try {
        const response = await fetch('/api/voice-config')
        if (!response.ok) return null
        return normalizeMsalConfig(await response.json())
      } catch {
        return null
      }
    })()
  }
  return cachedMsalConfigPromise
}

export interface DelegatedApiAuthResult {
  headers: Record<string, string>
  status: DelegatedAuthStatus
}

export async function getDelegatedApiAuth(options?: { interactive?: boolean }): Promise<DelegatedApiAuthResult> {
  const config = await getMsalConfig()
  if (!config) {
    return { headers: {}, status: 'unavailable' }
  }

  const result = await getWorkIqGraphAuth(config, options?.interactive === true)
  return {
    headers: result.token ? { Authorization: `Bearer ${result.token}` } : {},
    status: result.status,
  }
}

export async function getDelegatedApiHeaders(options?: { interactive?: boolean }): Promise<Record<string, string>> {
  return (await getDelegatedApiAuth(options)).headers
}

export function resetDelegatedApiAuthCache(): void {
  cachedMsalConfigPromise = null
}
