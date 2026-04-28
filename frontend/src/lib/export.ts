/**
 * エクスポートユーティリティ。成果物をダウンロードする。
 */

import type { ImageContent, TextContent } from '../hooks/useSSE'
import { sanitizeImageUrl, sanitizeLinkUrl } from './safe-url'

function findLastContent(
  contents: TextContent[],
  predicate: (content: TextContent) => boolean,
): TextContent | undefined {
  for (let index = contents.length - 1; index >= 0; index -= 1) {
    if (predicate(contents[index])) {
      return contents[index]
    }
  }
  return undefined
}

function sanitizeHtmlForExport(html: string): string {
  const documentFragment = new DOMParser().parseFromString(html, 'text/html')
  const blockedTags = ['script', 'iframe', 'form', 'object', 'embed', 'base', 'meta']

  blockedTags.forEach(tagName => {
    documentFragment.querySelectorAll(tagName).forEach(node => node.remove())
  })

  documentFragment.querySelectorAll('*').forEach(node => {
    Array.from(node.attributes).forEach(attribute => {
      const attributeName = attribute.name.toLowerCase()
      if (attributeName.startsWith('on')) {
        node.removeAttribute(attribute.name)
      }
      if (attributeName === 'href' && !sanitizeLinkUrl(attribute.value)) {
        node.removeAttribute(attribute.name)
      }
      if (attributeName === 'src' && !sanitizeImageUrl(attribute.value)) {
        node.removeAttribute(attribute.name)
      }
    })
  })

  return documentFragment.documentElement.outerHTML
}

function downloadBlob(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function downloadImageUrl(imageUrl: string, filename: string) {
  const safeUrl = sanitizeImageUrl(imageUrl)
  if (!safeUrl) return

  const a = document.createElement('a')
  a.href = safeUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

/** 企画書を Markdown ファイルとしてダウンロード */
export function exportPlanMarkdown(contents: TextContent[]) {
  const revised = findLastContent(contents, c => c.agent === 'plan-revision-agent')
  const plan = revised || findLastContent(contents, c => c.agent === 'marketing-plan-agent')
  if (!plan) return
  downloadBlob(plan.content, 'marketing-plan.md', 'text/markdown;charset=utf-8')
}

/** ブローシャを HTML ファイルとしてダウンロード */
export function exportBrochureHtml(contents: TextContent[]) {
  const brochure = findLastContent(contents, c => c.agent === 'brochure-gen-agent' && c.content_type === 'html')
  if (!brochure) return
  downloadBlob(sanitizeHtmlForExport(brochure.content), 'brochure.html', 'text/html;charset=utf-8')
}

/** 画像を PNG としてダウンロード */
export function exportImage(image: ImageContent, index: number) {
  downloadImageUrl(image.url, `image-${index + 1}.png`)
}

/** 全成果物を JSON で一括エクスポート */
export function exportAllAsJson(
  contents: TextContent[],
  images: ImageContent[],
  conversationId: string | null,
) {
  const data = {
    metadata: {
      conversation_id: conversationId,
      exported_at: new Date().toISOString(),
    },
    plan: findLastContent(contents, c => c.agent === 'marketing-plan-agent')?.content || null,
    revised_plan: findLastContent(contents, c => c.agent === 'plan-revision-agent')?.content || null,
    regulation_check: findLastContent(contents, c => c.agent === 'regulation-check-agent')?.content || null,
    brochure_html: findLastContent(contents, c => c.agent === 'brochure-gen-agent' && c.content_type === 'html')?.content || null,
    analysis: findLastContent(contents, c => c.agent === 'data-search-agent')?.content || null,
    images: images.map(img => ({ url: sanitizeImageUrl(img.url) ?? null, alt: img.alt })),
  }
  downloadBlob(JSON.stringify(data, null, 2), 'artifacts.json', 'application/json;charset=utf-8')
}
