import { Clock, FileText, Wrench } from 'lucide-react'
import type { PipelineMetrics } from '../hooks/useSSE'

interface MetricsBarProps {
  metrics: PipelineMetrics | null
  t: (key: string) => string
  locale: string
}

export function MetricsBar({ metrics, t, locale }: MetricsBarProps) {
  if (!metrics) return null

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-full border border-[var(--panel-border)] bg-[var(--panel-strong)] px-4 py-2 text-xs text-[var(--text-secondary)]">
      <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" /> {t('metrics.latency')}: {metrics.latency_seconds}s</span>
      <span className="inline-flex items-center gap-1"><Wrench className="h-3 w-3" /> {t('metrics.tools')}: {metrics.tool_calls}</span>
      {metrics.total_tokens > 0 && (
        <span className="inline-flex items-center gap-1"><FileText className="h-3 w-3" /> {t('metrics.tokens')}: {metrics.total_tokens.toLocaleString(locale)}</span>
      )}
    </div>
  )
}
