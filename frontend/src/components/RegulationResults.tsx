import type { TextContent } from '../hooks/useSSE'
import { MarkdownView } from './MarkdownView'

interface RegulationResultsProps {
  contents: TextContent[]
  t: (key: string) => string
}

export function RegulationResults({ contents, t }: RegulationResultsProps) {
  const regulationContent = contents.find(c => c.agent === 'regulation-check-agent')
  if (!regulationContent) return null

  return (
    <div className="rounded-[24px] border border-emerald-200 bg-emerald-50 p-5 dark:border-emerald-900 dark:bg-emerald-950/60">
      <h3 className="mb-3 text-sm font-medium text-emerald-800 dark:text-emerald-300">
        {t('section.regulation')}
      </h3>
      <MarkdownView content={regulationContent.content} />
    </div>
  )
}
