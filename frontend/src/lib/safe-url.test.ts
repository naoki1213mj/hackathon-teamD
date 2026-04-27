import { describe, expect, it } from 'vitest'
import {
  isSafeDataImageUrl,
  sanitizeHttpUrl,
  sanitizeImageUrl,
  sanitizeLinkUrl,
  stripResponseCitationMarkers,
} from './safe-url'

describe('safe URL helpers', () => {
  it('allows expected link protocols and blocks dangerous protocols', () => {
    expect(sanitizeLinkUrl('https://example.com/report')).toBe('https://example.com/report')
    expect(sanitizeLinkUrl('http://example.com/report')).toBe('http://example.com/report')
    expect(sanitizeLinkUrl('mailto:team@example.com')).toBe('mailto:team@example.com')
    expect(sanitizeLinkUrl('tel:+81312345678')).toBe('tel:+81312345678')
    expect(sanitizeLinkUrl('javascript:alert(1)')).toBeUndefined()
    expect(sanitizeLinkUrl('java\nscript:alert(1)')).toBeUndefined()
    expect(sanitizeLinkUrl('data:text/html,<script>alert(1)</script>')).toBeUndefined()
    expect(sanitizeLinkUrl('vbscript:msgbox(1)')).toBeUndefined()
    expect(sanitizeLinkUrl('file:///C:/secret.txt')).toBeUndefined()
    expect(sanitizeLinkUrl('blob:https://example.com/id')).toBeUndefined()
  })

  it('allows only http and https for generic HTTP URLs', () => {
    expect(sanitizeHttpUrl('https://example.com')).toBe('https://example.com')
    expect(sanitizeHttpUrl('mailto:team@example.com')).toBeUndefined()
    expect(sanitizeHttpUrl('https://example.com/report?sig=secret')).toBeUndefined()
  })

  it('allows HTTP(S) and sanitized data images for images', () => {
    const svg = 'data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Ctext%3Eplaceholder%3C%2Ftext%3E%3C%2Fsvg%3E'

    expect(sanitizeImageUrl('https://example.com/image.png')).toBe('https://example.com/image.png')
    expect(sanitizeImageUrl('data:image/png;base64,abc123+/=')).toBe('data:image/png;base64,abc123+/=')
    expect(isSafeDataImageUrl(svg)).toBe(true)
    expect(sanitizeImageUrl(svg)).toBe(svg)
  })

  it('blocks unsafe image URLs and active SVG data images', () => {
    expect(sanitizeImageUrl('javascript:alert(1)')).toBeUndefined()
    expect(sanitizeImageUrl('file:///C:/secret.png')).toBeUndefined()
    expect(sanitizeImageUrl('blob:https://example.com/id')).toBeUndefined()
    expect(sanitizeImageUrl('data:text/html,<script>alert(1)</script>')).toBeUndefined()
    expect(sanitizeImageUrl('data:image/svg+xml,<svg onload="alert(1)"></svg>')).toBeUndefined()
    expect(sanitizeImageUrl('data:image/svg+xml,<svg><script>alert(1)</script></svg>')).toBeUndefined()
  })
})

describe('stripResponseCitationMarkers', () => {
  it('strips raw Foundry/Web Search citation markers', () => {
    expect(stripResponseCitationMarkers('需要が高い。 \ue200cite\ue202turn0search0\ue201')).toBe('需要が高い。')
    expect(stripResponseCitationMarkers('市場は拡大中。 \ue200cite\ue202turn0search0, turn0search1\ue201')).toBe('市場は拡大中。')
  })

  it('preserves unchanged markdown spacing when citation markers are absent', () => {
    expect(stripResponseCitationMarkers('```text\n  keep  spacing\n```')).toBe('```text\n  keep  spacing\n```')
  })
})

