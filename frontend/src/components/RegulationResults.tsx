import type { TextContent } from '../hooks/useSSE'
import { MarkdownView } from './MarkdownView'

interface RegulationResultsProps {
  contents: TextContent[]
}

export function RegulationResults({ contents }: RegulationResultsProps) {
  const regulationContent = contents.find(c => c.agent === 'regulation-check-agent')
  if (!regulationContent) return null

  return (
    <div className="rounded-lg bg-green-50 p-4 dark:bg-green-950">
      <h3 className="mb-2 text-sm font-medium text-green-800 dark:text-green-300">
        ⚖️ レギュレーションチェック
      </h3>
      <MarkdownView content={regulationContent.content} />
    </div>
  )
}
