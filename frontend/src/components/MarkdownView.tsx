/**
 * Markdown レンダラーコンポーネント。react-markdown で安全に描画する。
 */

import ReactMarkdown from 'react-markdown'

interface MarkdownViewProps {
  content: string
  className?: string
}

export function MarkdownView({ content, className = '' }: MarkdownViewProps) {
  return (
    <div className={`prose prose-sm max-w-none dark:prose-invert ${className}`}>
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  )
}
