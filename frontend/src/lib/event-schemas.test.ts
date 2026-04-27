import { describe, expect, expectTypeOf, it } from 'vitest'
import {
  normalizeEvidenceItems,
  normalizeDebugEvents,
  normalizePipelineMetrics,
  normalizeSourceIngestionStates,
  normalizeTraceEvents,
  normalizeWorkIqSourceMetadata,
  type PipelineMetrics,
} from './event-schemas'

describe('event schema normalizers', () => {
  it('normalizes evidence items and blocks unsafe URLs', () => {
    const evidence = normalizeEvidenceItems([
      {
        id: 'ev-1',
        title: '需要データ',
        source: 'fabric',
        url: 'javascript:alert(1)',
        quote: 'Authorization: Bearer secret-token',
        relevance: 0.8,
        metadata: { region: 'okinawa', token: 'secret', nested: { ignored: true } },
      },
      { id: 'ev-2', source: 'web', url: 'https://example.com/report?sig=secret' },
      { title: 'source missing' },
    ])

    expect(evidence).toEqual([
      {
        id: 'ev-1',
        title: '需要データ',
        source: 'fabric',
        quote: '[redacted]',
        relevance: 0.8,
        metadata: { region: 'okinawa' },
      },
      {
        id: 'ev-2',
        source: 'web',
      },
    ])
  })

  it('keeps legacy metrics and additive schema fields', () => {
    const metrics = normalizePipelineMetrics({
      latency_seconds: 1.2,
      tool_calls: 3,
      total_tokens: 42,
      prompt_tokens: 10,
      completion_tokens: 32,
      estimated_cost_usd: 0.004,
      latency_by_agent_seconds: { 'data-search-agent': 0.7, bad: -1 },
      agent_tokens: { 'data-search-agent': 42, bad: -1 },
      agent_prompt_tokens: { 'data-search-agent': 10 },
      agent_completion_tokens: { 'data-search-agent': 32 },
      agent_estimated_costs_usd: { 'data-search-agent': 0.004 },
      evidence: [{ source: 'fabric', title: '売上履歴' }],
      charts: [{ chart_type: 'line', title: '需要推移', data: [{ month: '4月', sales: 1000 }] }],
      trace_events: [{ name: 'agent.run', duration_ms: 120 }],
      debug_events: [{ level: 'warning', message: 'fallback used' }],
      source_ingestion: [{ source: 'sharepoint', status: 'partial', items_ingested: 8 }],
    })

    expectTypeOf(metrics).toEqualTypeOf<PipelineMetrics | null>()
    expect(metrics).toMatchObject({
      latency_seconds: 1.2,
      tool_calls: 3,
      total_tokens: 42,
      prompt_tokens: 10,
      agent_latencies: { 'data-search-agent': 0.7 },
      agent_tokens: { 'data-search-agent': 42 },
      agent_prompt_tokens: { 'data-search-agent': 10 },
      agent_completion_tokens: { 'data-search-agent': 32 },
      agent_estimated_costs_usd: { 'data-search-agent': 0.004 },
    })
    expect(metrics?.evidence?.[0].source).toBe('fabric')
    expect(metrics?.charts?.[0].chart_type).toBe('line')
    expect(metrics?.trace_events?.[0].name).toBe('agent.run')
    expect(metrics?.debug_events?.[0].level).toBe('warning')
    expect(metrics?.source_ingestion?.[0].status).toBe('partial')
  })

  it('normalizes Work IQ source metadata with additive fields', () => {
    const metadata = normalizeWorkIqSourceMetadata([
      {
        source: 'emails',
        label: 'メール',
        count: 4,
        connector: 'outlook',
        status: 'completed',
        summary: '<b>家族向け</b> 需要を重視',
        preview: 'メールでは価格より体験価値を重視',
        confidence: 0.75,
        evidence_ids: ['ev-1', 'ev-1'],
      },
    ])

    expect(metadata).toEqual([
      {
        source: 'emails',
        label: 'メール',
        count: 4,
        connector: 'outlook',
        status: 'completed',
        summary: '家族向け 需要を重視',
        preview: 'メールでは価格より体験価値を重視',
        confidence: 0.75,
        evidence_ids: ['ev-1'],
      },
    ])
  })

  it('normalizes unknown source ingestion status without failing the payload', () => {
    expect(normalizeSourceIngestionStates([
      { source: 'sharepoint', status: 'queued', items_discovered: 12, items_failed: -1 },
    ])).toEqual([
      { source: 'sharepoint', status: 'unknown', items_discovered: 12 },
    ])
  })

  it('redacts sensitive trace and debug fields before UI rendering', () => {
    const traces = normalizeTraceEvents([
      {
        name: 'tool.call',
        metadata: {
          prompt: 'raw prompt should never render',
          region: 'okinawa',
          auth: 'Bearer abc.def',
        },
      },
    ])
    const debug = normalizeDebugEvents([
      {
        level: 'info',
        message: 'Authorization: Bearer abc.def',
        metadata: {
          transcript: 'raw meeting transcript',
          cache: 'hit',
        },
      },
      { message: '<html><body>brochure</body></html>' },
    ])

    expect(traces?.[0].metadata).toEqual({ region: 'okinawa' })
    expect(debug?.[0].message).toBe('[redacted]')
    expect(debug?.[0].metadata).toEqual({ cache: 'hit' })
    expect(debug?.[1].message).toBe('[redacted html]')
  })
})
