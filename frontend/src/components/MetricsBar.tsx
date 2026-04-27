import { Clock, DollarSign, FileText, Wrench } from 'lucide-react'
import type { PipelineMetrics } from '../hooks/useSSE'

interface MetricsBarProps {
  metrics: PipelineMetrics | null
  t: (key: string) => string
  locale: string
}

export function MetricsBar({ metrics, t, locale }: MetricsBarProps) {
  if (!metrics) return null

  const agentNames = Array.from(new Set([
    ...Object.keys(metrics.agent_latencies ?? {}),
    ...Object.keys(metrics.agent_tokens ?? {}),
    ...Object.keys(metrics.agent_estimated_costs_usd ?? {}),
  ])).sort()
  const formatCost = (value: number) => new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: value < 0.01 ? 6 : 4,
  }).format(value)

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-[var(--panel-border)] bg-[var(--panel-strong)] px-4 py-2 text-xs text-[var(--text-secondary)]">
      <span className="inline-flex items-center gap-1">
        <Clock className="h-3 w-3" /> {t('metrics.latency')}: {metrics.latency_seconds}s
      </span>
      <span className="inline-flex items-center gap-1">
        <Wrench className="h-3 w-3" /> {t('metrics.tools')}: {metrics.tool_calls}
      </span>
      {metrics.total_tokens > 0 && (
        <span className="inline-flex items-center gap-1">
          <FileText className="h-3 w-3" /> {t('metrics.tokens')}: {metrics.total_tokens.toLocaleString(locale)}
        </span>
      )}
      {metrics.estimated_cost_usd !== undefined && (
        <span className="inline-flex items-center gap-1">
          <DollarSign className="h-3 w-3" /> {t('metrics.estimated_cost')}: {formatCost(metrics.estimated_cost_usd)}
        </span>
      )}
      {agentNames.length > 0 && (
        <details className="basis-full text-[11px] text-[var(--text-muted)]">
          <summary className="cursor-pointer select-none py-1 font-medium text-[var(--text-secondary)]">
            {t('metrics.per_agent')}
          </summary>
          <div className="grid gap-1 pb-1 sm:grid-cols-2">
            {agentNames.map((agentName) => {
              const latency = metrics.agent_latencies?.[agentName]
              const tokens = metrics.agent_tokens?.[agentName]
              const cost = metrics.agent_estimated_costs_usd?.[agentName]
              return (
                <div key={agentName} className="rounded-xl bg-[var(--panel-bg)] px-3 py-2">
                  <span className="font-medium text-[var(--text-secondary)]">{agentName}</span>
                  <span className="ml-2">
                    {[
                      latency !== undefined ? `${latency}s` : null,
                      tokens !== undefined ? `${tokens.toLocaleString(locale)} ${t('metrics.tokens')}` : null,
                      cost !== undefined ? formatCost(cost) : null,
                    ].filter(Boolean).join(' · ')}
                  </span>
                </div>
              )
            })}
          </div>
        </details>
      )}
    </div>
  )
}
