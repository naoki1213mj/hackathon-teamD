import { AlertCircle, BarChart3, Check, FileText, Palette, Pencil, Scale, ShieldCheck, UserCheck, Video } from 'lucide-react'
import type { AgentProgress } from '../hooks/useSSE'
import type { VideoWorkflowStatus } from '../lib/video-status'

const PHASE_ICONS: Record<string, React.ReactNode> = {
  'data-search-agent': <BarChart3 className="h-4 w-4" />,
  'marketing-plan-agent': <FileText className="h-4 w-4" />,
  'approval': <ShieldCheck className="h-4 w-4" />,
  'regulation-check-agent': <Scale className="h-4 w-4" />,
  'plan-revision-agent': <Pencil className="h-4 w-4" />,
  'manager-approval': <UserCheck className="h-4 w-4" />,
  'brochure-gen-agent': <Palette className="h-4 w-4" />,
  'video-gen-agent': <Video className="h-4 w-4" />,
}

const BASE_PHASES = [
  { key: 'data-search-agent', label: 'step.data_search' },
  { key: 'marketing-plan-agent', label: 'step.marketing_plan' },
  { key: 'approval', label: 'step.approval' },
  { key: 'regulation-check-agent', label: 'step.regulation' },
  { key: 'plan-revision-agent', label: 'step.plan_revision' },
]

const MANAGER_APPROVAL_PHASE = { key: 'manager-approval', label: 'step.manager_approval' }

function buildPhases(showManagerApprovalPhase: boolean) {
  return showManagerApprovalPhase
    ? [...BASE_PHASES, MANAGER_APPROVAL_PHASE, { key: 'brochure-gen-agent', label: 'step.brochure' }, { key: 'video-gen-agent', label: 'step.video' }]
    : [...BASE_PHASES, { key: 'brochure-gen-agent', label: 'step.brochure' }, { key: 'video-gen-agent', label: 'step.video' }]
}

interface PipelineStepperProps {
  progress: AgentProgress | null
  t: (key: string) => string
  showManagerApprovalPhase?: boolean
  managerApprovalActive?: boolean
  videoStatus?: VideoWorkflowStatus
}

export function PipelineStepper({
  progress,
  t,
  showManagerApprovalPhase = false,
  managerApprovalActive = false,
  videoStatus = 'idle',
}: PipelineStepperProps) {
  const phases = buildPhases(showManagerApprovalPhase)
  const currentAgent = managerApprovalActive ? 'manager-approval' : progress?.agent || ''
  const currentPhaseIndex = progress ? phases.findIndex(phase => phase.key === currentAgent) : -1

  return (
    <div className="overflow-x-auto pb-1">
      <div className="flex min-w-max items-center gap-1 py-3">
      {phases.map((step, i) => {
        const hasReachedStep = currentPhaseIndex >= i
        let isActive = i === currentPhaseIndex && progress?.status === 'running'
        let isCompleted = currentPhaseIndex > i ||
          (currentPhaseIndex === i && progress?.status === 'completed')
        let isIssue = false

        if (step.key === 'video-gen-agent') {
          isActive = videoStatus === 'pending'
          isCompleted = videoStatus === 'completed'
          isIssue = videoStatus === 'issue'
        }

        const isPending = !isActive && !isCompleted && !isIssue
        const isConnectorActive = step.key === 'video-gen-agent'
          ? hasReachedStep || videoStatus === 'pending' || videoStatus === 'completed' || videoStatus === 'issue'
          : hasReachedStep

        return (
          <div key={step.key} className="flex items-center gap-1">
            {i > 0 && (
              <div className={`h-0.5 w-6 ${isConnectorActive ? 'bg-[var(--accent)]' : 'bg-[var(--panel-border)]'}`} />
            )}
            <div className="flex flex-col items-center gap-1">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm
                  ${isCompleted ? 'bg-[var(--accent)] text-white dark:bg-teal-700' : ''}
                  ${isActive ? 'animate-pulse bg-[var(--accent-soft)] text-[var(--accent-strong)] ring-2 ring-[var(--accent)]/40' : ''}
                  ${isIssue ? 'bg-[var(--warning-surface)] text-[var(--warning-text)] ring-1 ring-[var(--warning-border)]' : ''}
                  ${isPending ? 'bg-[var(--panel-strong)] text-[var(--text-muted)]' : ''}`}
              >
                {isCompleted ? <Check className="h-4 w-4" /> : isIssue ? <AlertCircle className="h-4 w-4" /> : PHASE_ICONS[step.key]}
              </div>
              <span className={`text-xs whitespace-nowrap
                ${isActive ? 'font-medium text-[var(--accent-strong)]' : isIssue ? 'font-medium text-[var(--warning-text)]' : 'text-[var(--text-muted)]'}`}>
                {t(step.label)}
              </span>
            </div>
          </div>
        )
      })}
      </div>
    </div>
  )
}
