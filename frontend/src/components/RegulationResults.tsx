import type { TextContent, ToolEvent } from '../hooks/useSSE'
import { EvidencePanel } from './EvidencePanel'
import { MarkdownView } from './MarkdownView'

interface RegulationResultsProps {
  contents: TextContent[]
  toolEvents?: ToolEvent[]
  t: (key: string) => string
}

export function RegulationResults({ contents, toolEvents = [], t }: RegulationResultsProps) {
  const regulationContent = contents.findLast(c => c.agent === 'regulation-check-agent')
  if (!regulationContent) return null

  return (
    <div className="rounded-[24px] border border-[var(--success-border)] bg-[var(--success-surface)] p-5">
      <h3 className="mb-3 text-sm font-medium text-[var(--success-text)]">
        {t('section.regulation')}
      </h3>
      <MarkdownView content={regulationContent.content} />
      <EvidencePanel events={toolEvents} t={t} />
    </div>
  )
}
