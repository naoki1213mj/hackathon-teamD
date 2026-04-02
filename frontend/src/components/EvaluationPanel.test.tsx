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
    marketing_quality: { overall: 4 },
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
  const t = (key: string) => key

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

    fireEvent.click(screen.getByRole('button', { name: 'eval.run' }))

    await waitFor(() => {
      expect(onEvaluationRecorded).toHaveBeenCalledWith(expect.objectContaining({ version: 2, round: 2 }))
    })
  })

  it('shows comparison across refinement rounds', () => {
    const evaluationV2 = {
      version: 2,
      round: 1,
      createdAt: '2026-04-02T02:00:00+00:00',
      result: {
        builtin: { relevance: { score: 5, reason: 'great' } },
        marketing_quality: { overall: 5 },
      },
    }

    render(
      <EvaluationPanel
        query="q"
        response="plan B"
        html="<p>B</p>"
        artifactVersion={2}
        evaluations={[evaluationV2]}
        versions={[makeSnapshot(), makeSnapshot([evaluationV2])]}
        t={t}
      />,
    )

    expect(screen.getByText('eval.compare')).not.toBeNull()
    expect(screen.getByRole('button', { name: /v1/i })).not.toBeNull()
    expect(screen.getByRole('button', { name: /v2/i })).not.toBeNull()
  })
})
