/**
 * エクスポート関数のテスト
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { TextContent, ImageContent } from '../../hooks/useSSE'

let capturedBlobs: Blob[] = []

beforeEach(() => {
  capturedBlobs = []
  vi.restoreAllMocks()

  // URL.createObjectURL でBlobをキャプチャ
  globalThis.URL.createObjectURL = vi.fn((blob: Blob) => {
    capturedBlobs.push(blob)
    return 'blob:test'
  }) as typeof URL.createObjectURL
  globalThis.URL.revokeObjectURL = vi.fn()

  // <a> の click をモック
  const originalCreateElement = document.createElement.bind(document)
  vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
    const el = originalCreateElement(tag)
    if (tag === 'a') {
      el.click = vi.fn()
    }
    return el
  })
})

async function getCapturedText(): Promise<string> {
  if (capturedBlobs.length === 0) return ''
  return await capturedBlobs[capturedBlobs.length - 1].text()
}

describe('exportBrochureHtml', () => {
  it('sanitizes script tags', async () => {
    const { exportBrochureHtml } = await import('../export')
    const contents: TextContent[] = [
      { content: '<div>Hello</div><script>alert("xss")</script>', agent: 'brochure-gen-agent', content_type: 'html' },
    ]
    exportBrochureHtml(contents)
    const result = await getCapturedText()
    expect(result).not.toContain('<script>')
    expect(result).toContain('Hello')
  })

  it('sanitizes iframe tags', async () => {
    const { exportBrochureHtml } = await import('../export')
    const contents: TextContent[] = [
      { content: '<div>Safe</div><iframe src="evil.com"></iframe>', agent: 'brochure-gen-agent', content_type: 'html' },
    ]
    exportBrochureHtml(contents)
    const result = await getCapturedText()
    expect(result).not.toContain('<iframe')
    expect(result).toContain('Safe')
  })

  it('strips onXxx event attributes', async () => {
    const { exportBrochureHtml } = await import('../export')
    const contents: TextContent[] = [
      { content: '<div onclick="alert(1)" onmouseover="hack()">Clean</div>', agent: 'brochure-gen-agent', content_type: 'html' },
    ]
    exportBrochureHtml(contents)
    const result = await getCapturedText()
    expect(result).not.toContain('onclick')
    expect(result).not.toContain('onmouseover')
    expect(result).toContain('Clean')
  })

  it('strips javascript: URLs', async () => {
    const { exportBrochureHtml } = await import('../export')
    const contents: TextContent[] = [
      { content: '<a href="javascript:alert(1)">Click</a>', agent: 'brochure-gen-agent', content_type: 'html' },
    ]
    exportBrochureHtml(contents)
    const result = await getCapturedText()
    expect(result).not.toContain('javascript:')
    expect(result).toContain('Click')
  })

  it('strips unsafe href and src protocols while keeping safe data images', async () => {
    const { exportBrochureHtml } = await import('../export')
    const contents: TextContent[] = [
      {
        content: [
          '<a href="vbscript:msgbox(1)">Bad link</a>',
          '<img src="file:///C:/secret.png" alt="bad" />',
          '<img src="data:image/png;base64,abc123" alt="ok" />',
          '<img src="data:image/svg+xml,<svg onload=&quot;alert(1)&quot;></svg>" alt="bad svg" />',
        ].join(''),
        agent: 'brochure-gen-agent',
        content_type: 'html',
      },
    ]

    exportBrochureHtml(contents)

    const result = await getCapturedText()
    expect(result).not.toContain('vbscript:')
    expect(result).not.toContain('file:///')
    expect(result).not.toContain('data:image/svg+xml')
    expect(result).toContain('data:image/png;base64,abc123')
  })
})

describe('exportPlanMarkdown', () => {
  it('extracts correct agent content', async () => {
    const { exportPlanMarkdown } = await import('../export')
    const contents: TextContent[] = [
      { content: 'wrong agent', agent: 'other-agent' },
      { content: '# Marketing Plan\nDetails here', agent: 'marketing-plan-agent' },
    ]
    exportPlanMarkdown(contents)
    const result = await getCapturedText()
    expect(result).toBe('# Marketing Plan\nDetails here')
  })

  it('prefers the latest revised plan when multiple rounds exist', async () => {
    const { exportPlanMarkdown } = await import('../export')
    const contents: TextContent[] = [
      { content: '# Plan v1', agent: 'marketing-plan-agent' },
      { content: '# Revised v1', agent: 'plan-revision-agent' },
      { content: '# Plan v2', agent: 'marketing-plan-agent' },
      { content: '# Revised v2', agent: 'plan-revision-agent' },
    ]

    exportPlanMarkdown(contents)

    const result = await getCapturedText()
    expect(result).toBe('# Revised v2')
  })
})

describe('exportAllAsJson', () => {
  it('includes all artifact types', async () => {
    const { exportAllAsJson } = await import('../export')
    const contents: TextContent[] = [
      { content: 'plan content', agent: 'marketing-plan-agent' },
      { content: 'reg content', agent: 'regulation-check-agent' },
      { content: '<h1>brochure</h1>', agent: 'brochure-gen-agent', content_type: 'html' },
      { content: 'analysis content', agent: 'data-search-agent' },
    ]
    const images: ImageContent[] = [
      { url: 'data:image/png;base64,abc', alt: 'hero', agent: 'brochure-gen-agent' },
    ]
    exportAllAsJson(contents, images, 'conv-123')
    const result = await getCapturedText()
    const parsed = JSON.parse(result)
    expect(parsed.metadata.conversation_id).toBe('conv-123')
    expect(parsed.plan).toBe('plan content')
    expect(parsed.regulation_check).toBe('reg content')
    expect(parsed.brochure_html).toBe('<h1>brochure</h1>')
    expect(parsed.analysis).toBe('analysis content')
    expect(parsed.images).toHaveLength(1)
    expect(parsed.images[0].url).toBe('data:image/png;base64,abc')
  })

  it('uses the latest artifacts for multi-round exports', async () => {
    const { exportAllAsJson } = await import('../export')
    const contents: TextContent[] = [
      { content: 'plan v1', agent: 'marketing-plan-agent' },
      { content: 'revised v1', agent: 'plan-revision-agent' },
      { content: 'reg v1', agent: 'regulation-check-agent' },
      { content: '<h1>brochure v1</h1>', agent: 'brochure-gen-agent', content_type: 'html' },
      { content: 'analysis v1', agent: 'data-search-agent' },
      { content: 'plan v2', agent: 'marketing-plan-agent' },
      { content: 'revised v2', agent: 'plan-revision-agent' },
      { content: 'reg v2', agent: 'regulation-check-agent' },
      { content: '<h1>brochure v2</h1>', agent: 'brochure-gen-agent', content_type: 'html' },
      { content: 'analysis v2', agent: 'data-search-agent' },
    ]

    exportAllAsJson(contents, [], 'conv-latest')

    const parsed = JSON.parse(await getCapturedText())
    expect(parsed.plan).toBe('plan v2')
    expect(parsed.revised_plan).toBe('revised v2')
    expect(parsed.regulation_check).toBe('reg v2')
    expect(parsed.brochure_html).toBe('<h1>brochure v2</h1>')
    expect(parsed.analysis).toBe('analysis v2')
  })

  it('redacts unsafe and tokenized image URLs from JSON bundle', async () => {
    const { exportAllAsJson } = await import('../export')
    const images: ImageContent[] = [
      { url: 'https://example.com/hero.png?sig=secret', alt: 'tokenized', agent: 'brochure-gen-agent' },
      { url: 'javascript:alert(1)', alt: 'unsafe', agent: 'brochure-gen-agent' },
      { url: 'https://example.com/safe.png', alt: 'safe', agent: 'brochure-gen-agent' },
    ]

    exportAllAsJson([], images, 'conv-images')

    const parsed = JSON.parse(await getCapturedText())
    expect(parsed.images).toEqual([
      { url: null, alt: 'tokenized' },
      { url: null, alt: 'unsafe' },
      { url: 'https://example.com/safe.png', alt: 'safe' },
    ])
  })
})
