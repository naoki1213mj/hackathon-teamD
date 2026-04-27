import { BarChart3, ExternalLink, ShieldCheck } from 'lucide-react'
import type { ChartSpec, EvidenceItem, JsonScalar } from '../lib/event-schemas'
import { sanitizeHttpUrl } from '../lib/safe-url'

interface EvidenceChartPanelProps {
  evidence?: EvidenceItem[]
  charts?: ChartSpec[]
  t: (key: string) => string
  compact?: boolean
}

function formatScalar(value: JsonScalar | undefined): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'number') return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 2 })
  return String(value)
}

function getNumericKeys(rows: Record<string, JsonScalar>[]): string[] {
  return Array.from(new Set(rows.flatMap(row => (
    Object.entries(row)
      .filter(([, value]) => typeof value === 'number')
      .map(([key]) => key)
  ))))
}

function getLabelKey(rows: Record<string, JsonScalar>[], numericKeys: string[]): string | undefined {
  return Object.keys(rows[0] ?? {}).find(key => !numericKeys.includes(key))
}

function renderMiniChart(chart: ChartSpec) {
  const rows = chart.data ?? []
  if (rows.length === 0) return null

  const numericKeys = getNumericKeys(rows)
  const primaryNumericKey = chart.series?.find(key => numericKeys.includes(key)) ?? numericKeys[0]
  if (!primaryNumericKey) return null

  const labelKey = getLabelKey(rows, numericKeys)
  const values = rows.map(row => Number(row[primaryNumericKey] ?? 0)).filter(Number.isFinite)
  const max = Math.max(...values, 1)

  return (
    <div className="space-y-1.5">
      {rows.slice(0, 6).map((row, index) => {
        const rawValue = Number(row[primaryNumericKey] ?? 0)
        const value = Number.isFinite(rawValue) ? rawValue : 0
        const width = `${Math.max(4, Math.round((value / max) * 100))}%`
        return (
          <div key={`${chart.title ?? chart.chart_type}-${index}`} className="grid grid-cols-[minmax(72px,0.8fr)_minmax(120px,2fr)_auto] items-center gap-2 text-[11px]">
            <span className="truncate text-[var(--text-muted)]">{formatScalar(labelKey ? row[labelKey] : index + 1)}</span>
            <span className="h-2 overflow-hidden rounded-full bg-[var(--panel-border)]">
              <span className="block h-full rounded-full bg-[var(--accent)]" style={{ width }} />
            </span>
            <span className="tabular-nums text-[var(--text-secondary)]">{formatScalar(row[primaryNumericKey])}</span>
          </div>
        )
      })}
    </div>
  )
}

function renderChartTable(chart: ChartSpec) {
  const rows = chart.data ?? []
  if (rows.length === 0) return null
  const columns = Array.from(new Set(rows.flatMap(row => Object.keys(row)))).slice(0, 5)

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-[11px]">
        <thead className="text-[var(--text-muted)]">
          <tr>
            {columns.map(column => <th key={column} className="px-2 py-1 font-medium">{column}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 5).map((row, rowIndex) => (
            <tr key={`${chart.title ?? chart.chart_type}-${rowIndex}`} className="border-t border-[var(--panel-border)]">
              {columns.map(column => <td key={column} className="px-2 py-1 text-[var(--text-secondary)]">{formatScalar(row[column])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function EvidenceChartPanel({ evidence = [], charts = [], t, compact = false }: EvidenceChartPanelProps) {
  if (evidence.length === 0 && charts.length === 0) return null

  return (
    <div className={`grid gap-3 ${compact ? '' : 'py-2 md:grid-cols-2'}`}>
      {evidence.length > 0 && (
        <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--panel-bg)] p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h4 className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--text-primary)]">
              <ShieldCheck className="h-3.5 w-3.5 text-[var(--accent-strong)]" />
              {t('trace.evidence')}
            </h4>
            <span className="text-[10px] text-[var(--text-muted)]">{evidence.length}</span>
          </div>
          <div className="space-y-2">
            {evidence.slice(0, compact ? 2 : 4).map((item, index) => {
              const safeUrl = sanitizeHttpUrl(item.url)
              return (
                <div key={item.id ?? `${item.source}-${index}`} className="rounded-xl bg-[var(--panel-strong)] px-3 py-2">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-xs font-medium text-[var(--text-secondary)]">{item.title || item.source}</p>
                      <p className="mt-0.5 text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)]">{item.source}</p>
                    </div>
                    {safeUrl && (
                      <a href={safeUrl} target="_blank" rel="noopener noreferrer" className="text-[var(--accent-strong)]" aria-label={t('trace.evidence.open')}>
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    )}
                  </div>
                  {item.relevance !== undefined && (
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--panel-border)]" title={`${Math.round(item.relevance * 100)}%`}>
                      <span className="block h-full rounded-full bg-[var(--accent)]" style={{ width: `${Math.round(item.relevance * 100)}%` }} />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {charts.length > 0 && (
        <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--panel-bg)] p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h4 className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--text-primary)]">
              <BarChart3 className="h-3.5 w-3.5 text-[var(--accent-strong)]" />
              {t('trace.charts')}
            </h4>
            <span className="text-[10px] text-[var(--text-muted)]">{charts.length}</span>
          </div>
          <div className="space-y-3">
            {charts.slice(0, compact ? 1 : 3).map((chart, index) => (
              <div key={`${chart.title ?? chart.chart_type}-${index}`} className="space-y-2 rounded-xl bg-[var(--panel-strong)] px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-medium text-[var(--text-secondary)]">{chart.title || t('trace.chart.untitled')}</p>
                  <span className="rounded-full border border-[var(--panel-border)] px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)]">
                    {chart.chart_type}
                  </span>
                </div>
                {renderMiniChart(chart) ?? renderChartTable(chart)}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
