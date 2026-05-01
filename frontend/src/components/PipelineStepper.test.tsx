import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PipelineStepper } from './PipelineStepper'

const t = (key: string) => ({
  'step.data_search': 'データ分析',
  'step.marketing_plan': '施策生成',
  'step.approval': '承認',
  'step.regulation': '規制チェック',
  'step.plan_revision': '企画書修正',
  'step.manager_approval': '上司承認',
  'step.brochure': '販促物生成',
  'step.video': '動画生成',
}[key] ?? key)

describe('PipelineStepper', () => {
  it('renders an extra manager approval phase when enabled', () => {
    render(
      <PipelineStepper
        progress={{ agent: 'plan-revision-agent', status: 'running', step: 4, total_steps: 5 }}
        t={t}
        showManagerApprovalPhase
      />,
    )

    expect(screen.getByText('上司承認')).toBeInTheDocument()
  })

  it('shows manager approval as the active phase while manager approval is pending', () => {
    render(
      <PipelineStepper
        progress={{ agent: 'approval', status: 'running', step: 3, total_steps: 5 }}
        t={t}
        showManagerApprovalPhase
        managerApprovalActive
      />,
    )

    expect(screen.getByText('上司承認').className).toContain('font-medium')
  })

  it('keeps the video step active while avatar rendering is still pending', () => {
    render(
      <PipelineStepper
        progress={{ agent: 'video-gen-agent', status: 'completed', step: 5, total_steps: 5 }}
        t={t}
        videoStatus="pending"
      />,
    )

    expect(screen.getByText('動画生成').className).toContain('font-medium')
  })

  it('shows the video step as attention-needed when the video never materialized', () => {
    render(
      <PipelineStepper
        progress={{ agent: 'video-gen-agent', status: 'completed', step: 5, total_steps: 5 }}
        t={t}
        videoStatus="issue"
      />,
    )

    expect(screen.getByText('動画生成').className).toContain('text-[var(--warning-text)]')
  })

  it('does NOT show the video step as completed during a refine round (videoStatus=idle)', () => {
    // Regression test for the user-reported bug 2026-05-02: after a full pipeline run,
    // when the workflow regresses to "approval" state (refine round started), the video
    // step indicator was incorrectly showing GREEN CHECK because PipelineStepper read
    // videoStatus from the LAST committed version's content. The fix in App.tsx makes
    // stepperVideoContents empty during status='approval'/'running' with no pendingVersion,
    // so videoStatus drops to 'idle' and the chip shows the default Video icon, not check.
    const { container } = render(
      <PipelineStepper
        progress={{ agent: 'approval', status: 'running', step: 3, total_steps: 5 }}
        t={t}
        videoStatus="idle"
      />,
    )

    // Video step text should NOT have the active/completed font-medium styling
    const videoLabel = screen.getByText('動画生成')
    expect(videoLabel.className).not.toContain('font-medium')
    // No green check icon should be rendered for the video step (Check svg has data-testid?)
    // Instead the default Video icon. Best assertion: text-color stays muted.
    expect(videoLabel.className).toContain('text-[var(--text-muted)]')
    // sanity: no JSX errored
    expect(container.querySelector('[data-iq-active]')).toBeNull()
  })
})
