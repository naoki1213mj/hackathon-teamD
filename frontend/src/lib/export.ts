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

/**
 * data URL や http URL から画像拡張子を導出する。
 * rubber-duck `image-jpeg-fix-plan` SHOULD-FIX #1: GPT-Image を JPEG に
 * 切替えたあとも `.png` 固定でダウンロードすると拡張子が嘘になる。
 * 既知拡張子 (png/jpeg/jpg/gif/webp) のみ採用。未知は png にフォールバック。
 */
export function deriveImageExtension(url: string | null | undefined): string {
  if (!url) return 'png'
  const dataMatch = /^data:image\/([a-z0-9]+)[;,]/i.exec(url)
  if (dataMatch) {
    const mime = dataMatch[1].toLowerCase()
    if (mime === 'jpeg' || mime === 'jpg') return 'jpg'
    if (mime === 'png' || mime === 'gif' || mime === 'webp') return mime
    return 'png'
  }
  // http(s) URL: クエリ前のパスから拡張子を抽出
  const pathOnly = url.split('?')[0].split('#')[0]
  const extMatch = /\.([a-z0-9]+)$/i.exec(pathOnly)
  if (extMatch) {
    const ext = extMatch[1].toLowerCase()
    if (ext === 'jpeg') return 'jpg'
    if (ext === 'png' || ext === 'jpg' || ext === 'gif' || ext === 'webp') return ext
  }
  return 'png'
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

/** 画像をダウンロード (拡張子は MIME / URL から自動導出) */
export function exportImage(image: ImageContent, index: number) {
  const ext = deriveImageExtension(image.url)
  downloadImageUrl(image.url, `image-${index + 1}.${ext}`)
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
