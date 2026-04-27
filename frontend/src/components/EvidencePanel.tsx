import type { ChartSpec, EvidenceItem, JsonScalar } from '../lib/event-schemas'
import { sanitizeHttpUrl } from '../lib/safe-url'
import type { ToolEvent } from '../lib/tool-events'

interface EvidencePanelProps {
  events: ToolEvent[]
  t: (key: string) => string
}

function resolveSourceLabel(source: string, t: (key: string) => string): string {
  const normalized = source.trim().toLowerCase()
  const key = `evidence.source.${normalized}`
  const translated = t(key)
  return translated === key ? source.replaceAll('_', ' ') : translated
}

function stringifyScalar(value: JsonScalar | undefined): string {
  if (value === null || value === undefined) return ''
  return String(value)
}

function collectEvidence(events: ToolEvent[]): EvidenceItem[] {
  const byKey = new Map<string, EvidenceItem>()
  events.flatMap(event => event.evidence ?? []).forEach((item, index) => {
    const safeUrl = sanitizeHttpUrl(item.url)
    const key = item.id || safeUrl || `${item.source}:${item.title || index}`
    byKey.set(key, { ...item, url: safeUrl })
  })
  return Array.from(byKey.values()).slice(0, 8)
}

function collectCharts(events: ToolEvent[]): ChartSpec[] {
  return events.flatMap(event => event.charts ?? []).filter(chart => (chart.data?.length ?? 0) > 0).slice(0, 4)
}

function renderChartData(chart: ChartSpec) {
  const rows = chart.data ?? []
  const series = chart.series?.filter(key => rows.some(row => typeof row[key] === 'number')) ?? []
  const primarySeries = series[0]
  const labelKey = Object.keys(rows[0] ?? {}).find(key => key !== primarySeries)
  const maxValue = primarySeries
    ? Math.max(...rows.map(row => Number(row[primarySeries] || 0)), 1)
    : 1

  if (primarySeries && chart.chart_type !== 'table') {
    return (
      <div className="space-y-2">
        {rows.map((row, index) => {
          const value = Number(row[primarySeries] || 0)
          const label = stringifyScalar(labelKey ? row[labelKey] : `#${index + 1}`)
          return (
            <div key={`${label}-${index}`} className="grid grid-cols-[minmax(0,1fr)_96px] items-center gap-3">
              <span className="truncate text-[11px] text-[var(--text-muted)]">{label}</span>
              <div className="flex items-center gap-2">
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--panel-border)]">
                  <div
                    className="h-full rounded-full bg-[var(--accent)]"
                    style={{ width: `${Math.min((value / maxValue) * 100, 100)}%` }}
                  />
                </div>
                <span className="w-10 text-right text-[10px] text-[var(--text-muted)]">{value.toLocaleString()}</span>
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  const columns = Array.from(new Set(rows.flatMap(row => Object.keys(row)))).slice(0, 4)
  return (
    <div className="overflow-hidden rounded-xl border border-[var(--panel-border)]">
      <table className="w-full text-left text-[11px]">
        <thead className="bg-[var(--surface)] text-[var(--text-muted)]">
          <tr>
            {columns.map(column => <th key={column} className="px-2 py-1 font-medium">{column}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 5).map((row, rowIndex) => (
            <tr key={rowIndex} className="border-t border-[var(--panel-border)]">
              {columns.map(column => <td key={column} className="px-2 py-1 text-[var(--text-secondary)]">{stringifyScalar(row[column])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function EvidencePanel({ events, t }: EvidencePanelProps) {
  const evidence = collectEvidence(events)
  const charts = collectCharts(events)
  if (evidence.length === 0 && charts.length === 0) return null

  return (
    <div className="mt-4 space-y-3" data-testid="evidence-panel">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{t('evidence.title')}</h4>
        <span className="rounded-full border border-[var(--panel-border)] px-2 py-0.5 text-[10px] text-[var(--text-muted)]">
          {t('evidence.count').replace('{n}', String(evidence.length + charts.length))}
        </span>
      </div>

      {evidence.length > 0 && (
        <div className="grid gap-2 md:grid-cols-2">
          {evidence.map((item, index) => (
            <article key={item.id || `${item.source}-${index}`} className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface)] p-3">
              <div className="mb-2 flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-[var(--text-primary)]">{item.title || t('evidence.untitled')}</p>
                  <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--text-muted)]">{resolveSourceLabel(item.source, t)}</p>
                </div>
                {typeof item.relevance === 'number' && (
                  <span className="rounded-full bg-[var(--accent-soft)] px-2 py-0.5 text-[10px] font-medium text-[var(--accent-strong)]">
                    {Math.round(item.relevance * 100)}%
                  </span>
                )}
              </div>
              {item.quote && <p className="text-xs leading-relaxed text-[var(--text-secondary)]">“{item.quote}”</p>}
              {item.url && (
                <a className="mt-2 inline-flex text-xs font-medium text-[var(--accent-strong)] underline-offset-2 hover:underline" href={item.url} target="_blank" rel="noreferrer">
                  {t('evidence.open_source')}
                </a>
              )}
            </article>
          ))}
        </div>
      )}

      {charts.length > 0 && (
        <div className="grid gap-2 md:grid-cols-2">
          {charts.map((chart, index) => (
            <section key={`${chart.title || chart.chart_type}-${index}`} className="rounded-xl border border-[var(--panel-border)] bg-[var(--panel-strong)] p-3">
              <h5 className="mb-2 text-sm font-medium text-[var(--text-primary)]">{chart.title || t('evidence.chart')}</h5>
              {renderChartData(chart)}
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
