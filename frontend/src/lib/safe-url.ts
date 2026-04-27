const LINK_PROTOCOLS = new Set(['http:', 'https:', 'mailto:', 'tel:'])
const HTTP_PROTOCOLS = new Set(['http:', 'https:'])
const URL_SCHEME_RE = /^([a-zA-Z][a-zA-Z\d+.-]*):/
const RASTER_DATA_IMAGE_RE = /^data:image\/(?:png|jpe?g|gif|webp);base64,[a-z\d+/=\s]+$/i
const SVG_DATA_IMAGE_PREFIX = 'data:image/svg+xml'
const UNSAFE_SVG_CONTENT_RE = /<\s*(?:script|foreignObject|iframe|object|embed|link|style|image)\b|on[a-z]+\s*=|(?:javascript|vbscript|data:text\/html)\s*:/i
const SENSITIVE_QUERY_KEYS = new Set(['api_key', 'apikey', 'code', 'ocp-apim-subscription-key', 'secret', 'sig', 'subscription-key', 'token', 'x-functions-key'])
const PRIVATE_USE_RE = /[\uE000-\uF8FF]/
const RESPONSES_CITATION_RE = /[\s\uE000-\uF8FF]*cite[\uE000-\uF8FF]*(?:turn\d+[a-z_]+\d+(?:\s*,?\s*turn\d+[a-z_]+\d+)*)[\s\uE000-\uF8FF]*/gi

function toTrimmedString(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

function extractCompactProtocol(rawUrl: string): string | undefined {
  let compactUrl = ''
  for (const char of rawUrl.trim()) {
    const charCode = char.charCodeAt(0)
    if (charCode > 0x20 && charCode !== 0x7f) {
      compactUrl += char
    }
  }
  const match = URL_SCHEME_RE.exec(compactUrl)
  return match ? `${match[1].toLowerCase()}:` : undefined
}

function sanitizeAbsoluteUrl(value: unknown, allowedProtocols: Set<string>): string | undefined {
  const rawUrl = toTrimmedString(value)
  if (!rawUrl) return undefined

  const compactProtocol = extractCompactProtocol(rawUrl)
  if (!compactProtocol || !allowedProtocols.has(compactProtocol)) return undefined

  try {
    const parsed = new URL(rawUrl)
    for (const key of parsed.searchParams.keys()) {
      if (SENSITIVE_QUERY_KEYS.has(key.trim().toLowerCase())) return undefined
    }
    return allowedProtocols.has(parsed.protocol.toLowerCase()) ? rawUrl : undefined
  } catch {
    return undefined
  }
}

function decodeSvgDataPayload(payload: string, isBase64: boolean): string | undefined {
  try {
    return isBase64 ? atob(payload.replace(/\s+/g, '')) : decodeURIComponent(payload)
  } catch {
    return undefined
  }
}

export function isSafeDataImageUrl(value: unknown): boolean {
  const rawUrl = toTrimmedString(value)
  if (!rawUrl) return false
  if (RASTER_DATA_IMAGE_RE.test(rawUrl)) return true

  const commaIndex = rawUrl.indexOf(',')
  if (commaIndex < 0) return false

  const header = rawUrl.slice(0, commaIndex).toLowerCase()
  if (!header.startsWith(SVG_DATA_IMAGE_PREFIX)) return false

  const parameters = header
    .slice(SVG_DATA_IMAGE_PREFIX.length)
    .split(';')
    .filter(Boolean)
  const isBase64 = parameters.includes('base64')
  const hasUnexpectedParameter = parameters.some(parameter => parameter !== 'base64' && !parameter.startsWith('charset='))
  if (hasUnexpectedParameter) return false

  const decodedSvg = decodeSvgDataPayload(rawUrl.slice(commaIndex + 1), isBase64)
  if (!decodedSvg) return false

  return decodedSvg.trimStart().toLowerCase().startsWith('<svg') && !UNSAFE_SVG_CONTENT_RE.test(decodedSvg)
}

export function sanitizeHttpUrl(value: unknown): string | undefined {
  return sanitizeAbsoluteUrl(value, HTTP_PROTOCOLS)
}

export function sanitizeLinkUrl(value: unknown): string | undefined {
  return sanitizeAbsoluteUrl(value, LINK_PROTOCOLS)
}

export function sanitizeImageUrl(value: unknown): string | undefined {
  const rawUrl = toTrimmedString(value)
  if (!rawUrl) return undefined
  if (extractCompactProtocol(rawUrl) === 'data:') {
    return isSafeDataImageUrl(rawUrl) ? rawUrl : undefined
  }
  return sanitizeHttpUrl(rawUrl)
}

export function stripResponseCitationMarkers(value: string): string {
  const hasCitationMarker = RESPONSES_CITATION_RE.test(value) || PRIVATE_USE_RE.test(value)
  RESPONSES_CITATION_RE.lastIndex = 0
  if (!hasCitationMarker) return value

  const withoutMarkers = value
    .replace(RESPONSES_CITATION_RE, ' ')
    .replace(/[\uE000-\uF8FF]/g, '')
    .replace(/[ \t]+/g, ' ')
    .replace(/ *\n */g, '\n')

  return withoutMarkers.trim()
}

