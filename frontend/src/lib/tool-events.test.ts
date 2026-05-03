import { describe, expect, it } from 'vitest'
import { normalizeToolEventData } from './tool-events'

describe('normalizeToolEventData schema extensions', () => {
  it('preserves optional evidence, chart, trace, debug, source metadata, and ingestion fields', () => {
    const event = normalizeToolEventData(
      {
        tool: 'web_search',
        status: 'completed',
        agent: 'marketing-plan-agent',
        evidence: [{ source: 'web', url: 'https://example.com/report', relevance: 0.8 }],
        charts: [{ chart_type: 'bar', title: '需要' }],
        trace_events: [{ name: 'search.call', duration_ms: 20 }],
        debug_events: [{ message: 'cache hit', level: 'info' }],
        source_metadata: [{ source: 'meeting_notes', count: 2, connector: 'teams' }],
        source_ingestion: [{ source: 'fabric', status: 'completed', items_ingested: 10 }],
      },
      {
        fallbackVersion: 1,
        parseSourceScope: () => undefined,
      },
    )

    expect(event.provider).toBeUndefined()
    expect(event.evidence?.[0].url).toBe('https://example.com/report')
    expect(event.charts?.[0].chart_type).toBe('bar')
    expect(event.trace_events?.[0].name).toBe('search.call')
    expect(event.debug_events?.[0].level).toBe('info')
    expect(event.source_metadata?.[0].connector).toBe('teams')
    expect(event.source_ingestion?.[0].items_ingested).toBe(10)
  })

  // rubber-duck `bug1-fix-critique` non-blocking #1 反映:
  // 旧 backend (commit `c97b811` 以前) は `fabric_data_agent_invocation` などの
  // auxiliary telemetry event に `success` / `no_op` / `fallback` という
  // 非 canonical な status を emit していた。これらが Cosmos に persist された
  // conversation を restore した時、`toolStatusRank()` で rank 0 と判定され
  // chip が spinner のまま固定される。restore 時に canonical な terminal
  // status へ正規化することで、replay 時の stuck-spinner 退化を防ぐ。
  it('normalizes legacy success/succeeded/ok status to canonical completed', () => {
    for (const legacy of ['success', 'succeeded', 'ok']) {
      const event = normalizeToolEventData(
        { tool: 'fabric_data_agent_invocation', status: legacy, agent: 'data-search-agent' },
        { fallbackVersion: 1, parseSourceScope: () => undefined },
      )
      expect(event.status).toBe('completed')
    }
  })

  it('normalizes legacy no_op/noop/fallback status to canonical failed', () => {
    for (const legacy of ['no_op', 'noop', 'fallback']) {
      const event = normalizeToolEventData(
        { tool: 'fabric_data_agent_invocation', status: legacy, agent: 'data-search-agent' },
        { fallbackVersion: 1, parseSourceScope: () => undefined },
      )
      expect(event.status).toBe('failed')
    }
  })

  it('preserves canonical statuses unchanged', () => {
    for (const canonical of ['completed', 'running', 'failed', 'pending', 'queued', 'auth_required', 'error']) {
      const event = normalizeToolEventData(
        { tool: 'query_data_agent', status: canonical, agent: 'data-search-agent' },
        { fallbackVersion: 1, parseSourceScope: () => undefined },
      )
      expect(event.status).toBe(canonical)
    }
  })
})
