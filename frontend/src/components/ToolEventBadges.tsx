import type { ToolEvent } from '../hooks/useSSE'

const TOOL_ICONS: Record<string, string> = {
  search_sales_history: '📁',
  search_customer_reviews: '⭐',
  web_search: '🌐',
  foundry_iq_search: '📚',
  check_ng_expressions: '🔍',
  check_travel_law_compliance: '⚖️',
  generate_hero_image: '🖼️',
  generate_banner_image: '🎯',
}

interface ToolEventBadgesProps {
  events: ToolEvent[]
  t: (key: string) => string
}

export function ToolEventBadges({ events, t }: ToolEventBadgesProps) {
  if (events.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2 py-2">
      {events.map((event, i) => (
        <span
          key={`${event.tool}-${i}`}
          className="inline-flex items-center gap-2 rounded-full border border-[var(--panel-border)] bg-[var(--panel-strong)] px-3 py-1.5 text-xs text-[var(--text-secondary)]"
        >
          <span>{TOOL_ICONS[event.tool] || '🔧'}</span>
          <span>{t(`tool.${event.tool}`)}</span>
          <span className="text-[10px] uppercase tracking-[0.12em] text-[var(--text-muted)]">{event.agent}</span>
          <span className={event.status === 'completed' ? 'text-green-500' : 'text-yellow-500'}>
            {event.status === 'completed' ? '✓' : '⏳'}
          </span>
        </span>
      ))}
    </div>
  )
}
