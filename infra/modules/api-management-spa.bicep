// APIM SPA reverse proxy (D2 cutover)
// Browser → https://{apim}.azure-api.net/app/* → Container App backend
// 認証経路: Authorization: Bearer <Foundry user_impersonation token> を APIM が validate-jwt で検証
// 検証成功後、X-Apim-Trusted header (32-byte secret) を backend に注入し、backend は hmac.compare_digest で照合
// 静的アセット (SPA bundle) は anonymous で通過させる (rate-limit のみ)

@description('既存の APIM service 名 (このモジュールは新規 API を追加するだけ)')
param apimName string

@description('Container App の FQDN (ingress)')
param containerAppFqdn string

@description('Entra テナント ID')
param tenantId string

@description('frontend MSAL App Registration の client ID。空なら API は作成するが JWT validation はバイパス。')
param frontendClientId string = ''

@description('JWT audience (frontend 側 MSAL の取得スコープに対応する audience)')
param expectedJwtAudience string = 'https://ai.azure.com'

@description('APIM が backend に注入する trust header secret (32-byte hex 推奨)。空ならポリシー注入をスキップ。')
@secure()
param trustedAuthHeaderSecret string = ''

resource apim 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

// --- Named Values (tenant-id, frontend-client-id, expected-jwt-audience, trusted-auth-header-secret) ---
resource nvTenantId 'Microsoft.ApiManagement/service/namedValues@2024-06-01-preview' = {
  parent: apim
  name: 'tenant-id'
  properties: {
    displayName: 'tenant-id'
    value: tenantId
    secret: false
  }
}

resource nvAudience 'Microsoft.ApiManagement/service/namedValues@2024-06-01-preview' = {
  parent: apim
  name: 'expected-jwt-audience'
  properties: {
    displayName: 'expected-jwt-audience'
    value: expectedJwtAudience
    secret: false
  }
}

resource nvFrontendClientId 'Microsoft.ApiManagement/service/namedValues@2024-06-01-preview' = if (!empty(frontendClientId)) {
  parent: apim
  name: 'frontend-client-id'
  properties: {
    displayName: 'frontend-client-id'
    value: frontendClientId
    secret: false
  }
}

resource nvTrustedSecret 'Microsoft.ApiManagement/service/namedValues@2024-06-01-preview' = if (!empty(trustedAuthHeaderSecret)) {
  parent: apim
  name: 'trusted-auth-header-secret'
  properties: {
    displayName: 'trusted-auth-header-secret'
    value: trustedAuthHeaderSecret
    secret: true
  }
}

// --- API: SPA reverse proxy (path = "app") ---
resource spaApi 'Microsoft.ApiManagement/service/apis@2024-06-01-preview' = {
  parent: apim
  name: 'spa-app'
  properties: {
    displayName: 'Travel Marketing SPA'
    path: 'app'
    serviceUrl: 'https://${containerAppFqdn}'
    protocols: [
      'https'
    ]
    subscriptionRequired: false
    apiType: 'http'
  }
}

// --- Operations ---
// GET / (SPA root)
resource opGetRoot 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: spaApi
  name: 'get-root'
  properties: {
    displayName: 'GET /'
    method: 'GET'
    urlTemplate: '/'
  }
}

// HEAD /
resource opHeadRoot 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: spaApi
  name: 'head-root'
  properties: {
    displayName: 'HEAD /'
    method: 'HEAD'
    urlTemplate: '/'
  }
}

// * /{*path} (SPA static + /api/* catch-all)
// API-level policy で /app/api/* を JWT 検証、それ以外は anonymous で通過
// 注意: APIM template parameter `{path}` は単一 segment match。multi-segment 用に `{*path}` greedy form を使う
resource opCatchAllGet 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: spaApi
  name: 'catch-all-get'
  properties: {
    displayName: 'GET /{*path}'
    method: 'GET'
    urlTemplate: '/{*path}'
    templateParameters: [
      {
        name: 'path'
        type: 'string'
        required: false
        values: []
      }
    ]
  }
}

resource opCatchAllPost 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: spaApi
  name: 'catch-all-post'
  properties: {
    displayName: 'POST /{*path}'
    method: 'POST'
    urlTemplate: '/{*path}'
    templateParameters: [
      {
        name: 'path'
        type: 'string'
        required: false
        values: []
      }
    ]
  }
}

resource opCatchAllPut 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: spaApi
  name: 'catch-all-put'
  properties: {
    displayName: 'PUT /{*path}'
    method: 'PUT'
    urlTemplate: '/{*path}'
    templateParameters: [
      {
        name: 'path'
        type: 'string'
        required: false
        values: []
      }
    ]
  }
}

resource opCatchAllDelete 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: spaApi
  name: 'catch-all-delete'
  properties: {
    displayName: 'DELETE /{*path}'
    method: 'DELETE'
    urlTemplate: '/{*path}'
    templateParameters: [
      {
        name: 'path'
        type: 'string'
        required: false
        values: []
      }
    ]
  }
}

resource opCatchAllOptions 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: spaApi
  name: 'catch-all-options'
  properties: {
    displayName: 'OPTIONS /{*path}'
    method: 'OPTIONS'
    urlTemplate: '/{*path}'
    templateParameters: [
      {
        name: 'path'
        type: 'string'
        required: false
        values: []
      }
    ]
  }
}

// --- API-level inbound policy ---
// `loadTextContent()` で XML を外部ファイルから読む (Named Values で展開される)
// Named values: tenant-id, expected-jwt-audience, frontend-client-id, trusted-auth-header-secret
// frontendClientId / trustedAuthHeaderSecret が空のときは Named Value が作成されないため
// Bicep のレベルでは policy 注入をスキップし、従来 anonymous proxy として動かす
resource spaApiPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-06-01-preview' = if (!empty(frontendClientId) && !empty(trustedAuthHeaderSecret)) {
  parent: spaApi
  name: 'policy'
  properties: {
    format: 'xml'
    value: loadTextContent('apim-spa-policy.xml')
  }
  dependsOn: [
    nvTenantId
    nvAudience
    nvFrontendClientId
    nvTrustedSecret
  ]
}

// 開発時 / cutover 前は anonymous proxy だけにする (frontend / secret 未設定時)
resource spaApiPolicyAnonymous 'Microsoft.ApiManagement/service/apis/policies@2024-06-01-preview' = if (empty(frontendClientId) || empty(trustedAuthHeaderSecret)) {
  parent: spaApi
  name: 'policy'
  properties: {
    format: 'xml'
    value: '<policies><inbound><base /><rate-limit-by-key calls="600" renewal-period="60" counter-key="@((string)(context.Request.IpAddress ?? &quot;anonymous&quot;))" /></inbound><backend><forward-request timeout="600" buffer-response="false" /></backend><outbound><base /></outbound><on-error><base /></on-error></policies>'
  }
}

output apiId string = spaApi.id
output apiName string = spaApi.name
