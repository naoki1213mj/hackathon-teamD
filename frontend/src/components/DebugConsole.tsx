import { Bug, Filter } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { DebugEvent } from '../lib/event-schemas'

interface DebugConsoleProps {
  events: DebugEvent[]
  t: (key: string) => string
}

const LEVEL_STYLES: Record<DebugEvent['level'], string> = {
  debug: 'border-[var(--panel-border)] text-[var(--text-muted)]',
  info: 'border-sky-300/70 text-sky-700 dark:text-sky-200',
  warning: 'border-amber-300/80 text-amber-700 dark:text-amber-200',
  error: 'border-red-300/80 text-red-700 dark:text-red-200',
}

function uniqueAgents(events: DebugEvent[]): string[] {
  return Array.from(new Set(events.map(event => event.agent).filter((value): value is string => Boolean(value)))).sort()
}

export function DebugConsole({ events, t }: DebugConsoleProps) {
  const [levelFilter, setLevelFilter] = useState('')
  const [agentFilter, setAgentFilter] = useState('')
  const agents = useMemo(() => uniqueAgents(events), [events])
  const filteredEvents = useMemo(() => events.filter(event => (
    (!levelFilter || event.level === levelFilter)
    && (!agentFilter || event.agent === agentFilter)
  )), [agentFilter, events, levelFilter])

  if (events.length === 0) return null

  return (
    <section className="rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
          <Bug className="h-4 w-4 text-[var(--accent-strong)]" />
          {t('trace.debug_console')}
        </h3>
        <span className="text-xs text-[var(--text-muted)]">{t('trace.event_count').replace('{n}', String(filteredEvents.length))}</span>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
        <Filter className="h-3.5 w-3.5 text-[var(--text-muted)]" />
        <label className="inline-flex items-center gap-1 text-[var(--text-muted)]">
          <span>{t('trace.filter.level')}</span>
          <select
            value={levelFilter}
            onChange={event => setLevelFilter(event.target.value)}
            className="rounded-full border border-[var(--panel-border)] bg-[var(--panel-bg)] px-2 py-1 text-[var(--text-secondary)]"
          >
            <option value="">{t('trace.filter.all')}</option>
            {(['debug', 'info', 'warning', 'error'] as DebugEvent['level'][]).map(level => <option key={level} value={level}>{level}</option>)}
          </select>
        </label>
        <label className="inline-flex items-center gap-1 text-[var(--text-muted)]">
          <span>{t('trace.filter.agent')}</span>
          <select
            value={agentFilter}
            onChange={event => setAgentFilter(event.target.value)}
            className="rounded-full border border-[var(--panel-border)] bg-[var(--panel-bg)] px-2 py-1 text-[var(--text-secondary)]"
          >
            <option value="">{t('trace.filter.all')}</option>
            {agents.map(agent => <option key={agent} value={agent}>{agent}</option>)}
          </select>
        </label>
      </div>

      <div className="space-y-2">
        {filteredEvents.slice(0, 30).map((event, index) => (
          <article key={event.event_id ?? `${event.level}-${index}`} className="rounded-xl bg-[var(--panel-strong)] px-3 py-2 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] ${LEVEL_STYLES[event.level]}`}>
                {event.level}
              </span>
              {event.code && <span className="text-[10px] text-[var(--text-muted)]">{event.code}</span>}
              {event.agent && <span className="text-[10px] text-[var(--text-muted)]">{event.agent}</span>}
              {event.timestamp && <span className="text-[10px] text-[var(--text-muted)]">{event.timestamp}</span>}
            </div>
            <p className="mt-1 break-words text-[var(--text-secondary)]">{event.message}</p>
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
          </article>
        ))}
      </div>
    </section>
  )
}
