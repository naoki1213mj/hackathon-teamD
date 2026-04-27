import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { translations } from '../lib/i18n'
import { DebugConsole } from './DebugConsole'
import { EvidenceChartPanel } from './EvidenceChartPanel'
import { TraceViewer } from './TraceViewer'

const t = (key: string) => translations.en[key] ?? key

describe('workflow trace panels', () => {
  it('renders evidence links and dependency-free chart previews', () => {
    render(
      <EvidenceChartPanel
        t={t}
        evidence={[{ id: 'ev-1', title: 'Sales report', source: 'fabric', url: 'https://example.com/report', relevance: 0.8 }]}
        charts={[{ chart_type: 'bar', title: 'Demand', data: [{ month: 'Apr', sales: 120 }, { month: 'May', sales: 80 }] }]}
      />,
    )

    expect(screen.getByText('Evidence')).toBeInTheDocument()
    expect(screen.getByText('Sales report')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open evidence link' })).toHaveAttribute('href', 'https://example.com/report')
    expect(screen.getByText('Demand')).toBeInTheDocument()
    expect(screen.getByText('Apr')).toBeInTheDocument()
    expect(screen.getByText('120')).toBeInTheDocument()
  })

  it('filters trace events by status', () => {
    render(
      <TraceViewer
        t={t}
        events={[
          { name: 'agent.run', status: 'completed', agent: 'marketing-plan-agent', duration_ms: 42 },
          { name: 'tool.call', status: 'failed', tool: 'web_search' },
        ]}
      />,
    )

    expect(screen.getByText('agent.run')).toBeInTheDocument()
    expect(screen.getByText('tool.call')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'failed' } })

    expect(screen.queryByText('agent.run')).toBeNull()
    expect(screen.getByText('tool.call')).toBeInTheDocument()
  })

  it('filters debug console entries by level', () => {
    render(
      <DebugConsole
        t={t}
        events={[
          { level: 'info', message: 'cache hit', agent: 'data-search-agent' },
          { level: 'error', message: '[redacted]', code: 'SAFE_DEBUG' },
        ]}
      />,
    )

    expect(screen.getByText('cache hit')).toBeInTheDocument()
    expect(screen.getByText('[redacted]')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Level'), { target: { value: 'error' } })

    expect(screen.queryByText('cache hit')).toBeNull()
    expect(screen.getByText('[redacted]')).toBeInTheDocument()
  })
})
