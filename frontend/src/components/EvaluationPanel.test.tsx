import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { EvaluationPanel } from './EvaluationPanel'

const originalFetch = globalThis.fetch

const evaluationV1 = {
  version: 1,
  round: 1,
  createdAt: '2026-04-02T00:00:00+00:00',
  result: {
    builtin: { relevance: { score: 4, reason: 'good' } },
    marketing_quality: { overall: 4, appeal: 4, differentiation: 3, kpi_validity: 4, brand_tone: 4 },
    custom: {
      travel_law_compliance: { score: 1, details: { disclaimer: true, fee_display: false } },
    },
  },
}

const evaluationV2 = {
  version: 2,
  round: 1,
  createdAt: '2026-04-02T02:00:00+00:00',
  result: {
    builtin: { relevance: { score: 5, reason: 'great' } },
    marketing_quality: { overall: 5, appeal: 5, differentiation: 5, kpi_validity: 4, brand_tone: 5 },
    custom: {
      travel_law_compliance: { score: 1, details: { disclaimer: true, fee_display: true } },
    },
  },
}

function makeSnapshot(evaluations = [evaluationV1]) {
  return {
    textContents: [],
    images: [],
    toolEvents: [],
    metrics: null,
    evaluations,
  }
}

function createJsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('EvaluationPanel', () => {
  const mockFetch = vi.fn()
  const t = (key: string) => ({
    'eval.run': 'Run Evaluation',
    'eval.compare': 'Improvement Round Comparison',
    'eval.round': 'Evaluation #{n}',
    'eval.compare.preview_hint': 'Comparison changes only inside this panel.',
    'eval.compare.selection': 'Comparing {current} against {target}',
    'eval.compare.improved': 'Improved',
    'eval.compare.degraded': 'Regressed',
    'eval.compare.unchanged': 'Unchanged',
    'eval.compare.detail_changes': 'Checks that changed state',
    'eval.builtin': 'AI Quality Metrics',
    'eval.marketing': 'Appeal & Brand Quality',
    'eval.compliance': 'Compliance & Conversion',
    'eval.relevance': 'Relevance',
    'eval.travel_law_compliance': 'Travel Law',
  }[key] ?? key)

  beforeEach(() => {
    globalThis.fetch = mockFetch
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('keeps evaluation history separated by artifact version', async () => {
    const { rerender } = render(
      <EvaluationPanel
        query="q"
        response="plan A"
        html="<p>A</p>"
        artifactVersion={1}
        evaluations={[evaluationV1]}
        versions={[makeSnapshot()]}
        t={t}
      />,
    )

    expect(screen.getAllByText('4.0').length).toBeGreaterThan(0)

    rerender(
      <EvaluationPanel
        query="q"
        response="plan B"
        html="<p>B</p>"
        artifactVersion={2}
        evaluations={[]}
        versions={[makeSnapshot(), makeSnapshot([])]}
        t={t}
      />,
    )
    expect(screen.queryByText('4.0')).toBeNull()

    rerender(
      <EvaluationPanel
        query="q"
        response="plan A"
        html="<p>A</p>"
        artifactVersion={1}
        evaluations={[evaluationV1]}
        versions={[makeSnapshot(), makeSnapshot([])]}
        t={t}
      />,
    )

    expect(screen.getAllByText('4.0').length).toBeGreaterThan(0)
  })

  it('keeps evaluation visible when brochure html arrives later', async () => {
    const { rerender } = render(
      <EvaluationPanel
        query="q"
        response="plan A"
        html=""
        artifactVersion={1}
        evaluations={[evaluationV1]}
        versions={[makeSnapshot()]}
        t={t}
      />,
    )

    expect(screen.getAllByText('4.0').length).toBeGreaterThan(0)

    rerender(
      <EvaluationPanel
        query="q"
        response="plan A"
        html="<p>brochure ready</p>"
        artifactVersion={1}
        evaluations={[evaluationV1]}
        versions={[makeSnapshot()]}
        t={t}
      />,
    )

    expect(screen.getAllByText('4.0').length).toBeGreaterThan(0)
  })

  it('saves new evaluations through the version callback', async () => {
    mockFetch.mockResolvedValueOnce(createJsonResponse({
      builtin: { relevance: { score: 5, reason: 'great' } },
      evaluation_meta: { version: 2, round: 2, created_at: '2026-04-02T01:00:00+00:00' },
    }))

    const onEvaluationRecorded = vi.fn()

    render(
      <EvaluationPanel
        query="q"
        response="plan B"
        html="<p>B</p>"
        conversationId="conv-1"
        artifactVersion={2}
        evaluations={[]}
        versions={[makeSnapshot(), makeSnapshot([])]}
        onEvaluationRecorded={onEvaluationRecorded}
        t={t}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Run Evaluation' }))

    await waitFor(() => {
      expect(onEvaluationRecorded).toHaveBeenCalledWith(expect.objectContaining({ version: 2, round: 2 }))
    })
  })

  it('shows detailed comparison across versions without switching the preview', () => {
    render(
      <EvaluationPanel
        query="q"
        response="plan A"
        html="<p>B</p>"
        artifactVersion={1}
        evaluations={[evaluationV1]}
        versions={[makeSnapshot([evaluationV1]), makeSnapshot([evaluationV2])]}
        t={t}
      />,
    )

    expect(screen.getByText('Improvement Round Comparison')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /v2/i }))

    expect(screen.getByText('Comparing v1 against v2')).not.toBeNull()
    expect(screen.getByText('Improved')).not.toBeNull()
    expect(screen.getByText('Checks that changed state')).not.toBeNull()
    expect(screen.getAllByText(/fee_display/).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Relevance').length).toBeGreaterThan(0)
  })
})
