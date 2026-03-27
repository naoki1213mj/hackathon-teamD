import type { TextContent } from '../hooks/useSSE'
import { MarkdownView } from './MarkdownView'

interface AnalysisViewProps {
  contents: TextContent[]
}

export function AnalysisView({ contents }: AnalysisViewProps) {
  const analysisContent = contents.find(c => c.agent === 'data-search-agent')
  if (!analysisContent) return null

  return (
    <div className="rounded-lg bg-blue-50 p-4 dark:bg-blue-950">
      <h3 className="mb-2 text-sm font-medium text-blue-800 dark:text-blue-300">
        📊 データ分析結果
      </h3>
      <MarkdownView content={analysisContent.content} />
    </div>
  )
}
