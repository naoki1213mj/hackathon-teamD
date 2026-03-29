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
})
