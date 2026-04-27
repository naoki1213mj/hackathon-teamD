import { Activity, Filter } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { TraceEvent } from '../lib/event-schemas'

interface TraceViewerProps {
  events: TraceEvent[]
  t: (key: string) => string
}

function uniqueValues(events: TraceEvent[], key: 'agent' | 'tool' | 'status'): string[] {
  return Array.from(new Set(events.map(event => event[key]).filter((value): value is string => Boolean(value)))).sort()
}

function formatDuration(durationMs: number | undefined): string {
  if (durationMs === undefined) return ''
  return durationMs >= 1000 ? `${(durationMs / 1000).toFixed(1)}s` : `${Math.round(durationMs)}ms`
}

export function TraceViewer({ events, t }: TraceViewerProps) {
  const [agentFilter, setAgentFilter] = useState('')
  const [toolFilter, setToolFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const agents = useMemo(() => uniqueValues(events, 'agent'), [events])
  const tools = useMemo(() => uniqueValues(events, 'tool'), [events])
  const statuses = useMemo(() => uniqueValues(events, 'status'), [events])
  const filteredEvents = useMemo(() => events.filter(event => (
    (!agentFilter || event.agent === agentFilter)
    && (!toolFilter || event.tool === toolFilter)
    && (!statusFilter || event.status === statusFilter)
  )), [agentFilter, events, statusFilter, toolFilter])

  if (events.length === 0) return null

  return (
    <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
          <Activity className="h-4 w-4 text-[var(--accent-strong)]" />
          {t('trace.viewer')}
        </h3>
        <span className="text-xs text-[var(--text-muted)]">{t('trace.event_count').replace('{n}', String(filteredEvents.length))}</span>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
        <Filter className="h-3.5 w-3.5 text-[var(--text-muted)]" />
        {[
          { label: t('trace.filter.agent'), value: agentFilter, setter: setAgentFilter, options: agents },
          { label: t('trace.filter.tool'), value: toolFilter, setter: setToolFilter, options: tools },
          { label: t('trace.filter.status'), value: statusFilter, setter: setStatusFilter, options: statuses },
        ].map(filter => (
          <label key={filter.label} className="inline-flex items-center gap-1 text-[var(--text-muted)]">
            <span>{filter.label}</span>
            <select
              value={filter.value}
              onChange={event => filter.setter(event.target.value)}
              className="rounded-full border border-[var(--panel-border)] bg-[var(--panel-bg)] px-2 py-1 text-[var(--text-secondary)]"
            >
              <option value="">{t('trace.filter.all')}</option>
              {filter.options.map(option => <option key={option} value={option}>{option}</option>)}
            </select>
          </label>
        ))}
      </div>

      <ol className="space-y-2">
        {filteredEvents.slice(0, 30).map((event, index) => (
          <li key={event.event_id ?? `${event.name}-${index}`} className="rounded-xl bg-[var(--panel-strong)] px-3 py-2 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-[var(--text-secondary)]">{event.name}</span>
              {event.status && <span className="rounded-full border border-[var(--panel-border)] px-2 py-0.5 text-[10px] text-[var(--text-muted)]">{event.status}</span>}
              {event.duration_ms !== undefined && <span className="text-[10px] tabular-nums text-[var(--text-muted)]">{formatDuration(event.duration_ms)}</span>}
            </div>
            <div className="mt-1 flex flex-wrap gap-2 text-[10px] text-[var(--text-muted)]">
              {event.agent && <span>{t('trace.agent')}: {event.agent}</span>}
              {event.tool && <span>{t('trace.tool')}: {event.tool}</span>}
              {event.phase && <span>{t('trace.phase')}: {event.phase}</span>}
              {event.timestamp && <span>{event.timestamp}</span>}
            </div>
            {event.metadata && (
              <dl className="mt-2 grid gap-1 sm:grid-cols-2">
                {Object.entries(event.metadata).slice(0, 6).map(([key, value]) => (
                  <div key={key} className="rounded-lg bg-[var(--panel-bg)] px-2 py-1">
                    <dt className="text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)]">{key}</dt>
                    <dd className="break-words text-[11px] text-[var(--text-secondary)]">{String(value)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}
