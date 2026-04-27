/**
 * Markdown レンダラーコンポーネント。react-markdown で安全に描画する。
 */

import { memo } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { sanitizeImageUrl, sanitizeLinkUrl, stripResponseCitationMarkers } from '../lib/safe-url'

interface MarkdownViewProps {
  content: string
  className?: string
}

const markdownComponents: Components = {
  a({ href, title, children }) {
    const safeHref = sanitizeLinkUrl(href)
    if (!safeHref) return <span>{children}</span>

    return (
      <a href={safeHref} title={title} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    )
  },
  img({ src, alt, title }) {
    const safeSrc = sanitizeImageUrl(src)
    if (!safeSrc) return null

    return <img src={safeSrc} alt={alt ?? ''} title={title} loading="lazy" />
  },
}

function markdownUrlTransform(url: string, key: string): string {
  if (key === 'href') return sanitizeLinkUrl(url) ?? ''
  if (key === 'src') return sanitizeImageUrl(url) ?? ''
  return ''
}

export const MarkdownView = memo(function MarkdownView({ content, className = '' }: MarkdownViewProps) {
  const sanitizedContent = stripResponseCitationMarkers(content)

  return (
    <div
      className={[
        'prose prose-sm max-w-none dark:prose-invert',
        'text-[var(--text-secondary)]',
        'prose-headings:text-[var(--text-primary)] prose-headings:font-semibold',
        'prose-p:text-[var(--text-secondary)] prose-p:leading-relaxed',
        'prose-strong:text-[var(--text-primary)] prose-li:text-[var(--text-secondary)]',
        'prose-code:text-[var(--accent-strong)] prose-a:text-[var(--accent-strong)]',
        'prose-blockquote:border-[var(--accent)] prose-blockquote:text-[var(--text-secondary)]',
        'prose-hr:border-[var(--panel-border)]',
        'prose-pre:border prose-pre:border-[var(--panel-border)] prose-pre:bg-[var(--panel-strong)] prose-pre:rounded-lg',
        'prose-th:text-[var(--text-primary)] prose-th:font-medium prose-th:bg-[var(--panel-strong)] prose-th:px-3 prose-th:py-1.5',
        'prose-td:text-[var(--text-secondary)] prose-td:px-3 prose-td:py-1.5',
        'prose-table:border-collapse prose-table:w-full',
        '[&_table]:border [&_table]:border-[var(--panel-border)] [&_table]:rounded-lg',
        '[&_th]:border [&_th]:border-[var(--panel-border)]',
        '[&_td]:border [&_td]:border-[var(--panel-border)]',
        '[&_tr:nth-child(even)]:bg-[var(--panel-strong)]',
        className,
      ].join(' ')}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={markdownComponents}
        urlTransform={markdownUrlTransform}
      >
        {sanitizedContent}
      </ReactMarkdown>
    </div>
  )
})
