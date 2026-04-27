import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { ToolEvent } from '../hooks/useSSE'
import { EvidencePanel } from './EvidencePanel'

const t = (key: string) => ({
  'evidence.title': '根拠とデータ',
  'evidence.count': '{n}件',
  'evidence.untitled': '根拠ソース',
  'evidence.open_source': 'ソースを開く',
  'evidence.chart': 'データチャート',
  'evidence.source.fabric': 'Fabric Lakehouse',
  'evidence.source.foundry_iq': 'Foundry IQ',
  'evidence.source.web': 'Web Search',
  'evidence.source.local-check': 'ローカルチェック',
}[key] ?? key)

describe('EvidencePanel', () => {
  it('renders sanitized evidence cards and chart rows', () => {
    const events: ToolEvent[] = [
      {
        tool: 'search_sales_history',
        status: 'completed',
        agent: 'data-search-agent',
        evidence: [
          {
            id: 'sales',
            title: '販売履歴サマリ',
            source: 'fabric',
            quote: '沖縄プランが売上上位。',
            url: 'https://example.com/report',
            relevance: 0.91,
          },
          {
            id: 'unsafe',
            title: '危険 URL',
            source: 'web',
            url: 'javascript:alert(1)',
          },
        ],
        charts: [
          {
            chart_type: 'bar',
            title: '販売履歴 売上上位',
            series: ['revenue'],
            data: [{ plan: '沖縄', revenue: 1200 }],
          },
        ],
      },
    ]

    const { container } = render(<EvidencePanel events={events} t={t} />)

    expect(screen.getByText('根拠とデータ')).toBeInTheDocument()
    expect(screen.getByText('Fabric Lakehouse')).toBeInTheDocument()
    expect(screen.getByText('“沖縄プランが売上上位。”')).toBeInTheDocument()
    expect(screen.getByText('販売履歴 売上上位')).toBeInTheDocument()
    expect(container.querySelector('a[href="https://example.com/report"]')).not.toBeNull()
    expect(container.querySelector('a[href^="javascript:"]')).toBeNull()
  })
})
