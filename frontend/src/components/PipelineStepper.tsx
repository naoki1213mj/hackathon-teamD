import { BarChart3, Check, FileText, Palette, Pencil, Scale, ShieldCheck, UserCheck, Video } from 'lucide-react'
import type { AgentProgress } from '../hooks/useSSE'

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
}

export function PipelineStepper({
  progress,
  t,
  showManagerApprovalPhase = false,
  managerApprovalActive = false,
}: PipelineStepperProps) {
  const phases = buildPhases(showManagerApprovalPhase)
  const currentAgent = managerApprovalActive ? 'manager-approval' : progress?.agent || ''
  const currentPhaseIndex = progress ? phases.findIndex(phase => phase.key === currentAgent) : -1

  return (
    <div className="overflow-x-auto pb-1">
      <div className="flex min-w-max items-center gap-1 py-3">
      {phases.map((step, i) => {
        const isActive = i === currentPhaseIndex && progress?.status === 'running'
        const isCompleted = currentPhaseIndex > i ||
          (currentPhaseIndex === i && progress?.status === 'completed')
        const isPending = !isActive && !isCompleted

        return (
          <div key={step.key} className="flex items-center gap-1">
            {i > 0 && (
              <div className={`h-0.5 w-6 ${currentPhaseIndex >= i ? 'bg-[var(--accent)]' : 'bg-[var(--panel-border)]'}`} />
            )}
            <div className="flex flex-col items-center gap-1">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm
                  ${isCompleted ? 'bg-[var(--accent)] text-white dark:bg-teal-700' : ''}
                  ${isActive ? 'animate-pulse bg-[var(--accent-soft)] text-[var(--accent-strong)] ring-2 ring-[var(--accent)]/40' : ''}
                  ${isPending ? 'bg-[var(--panel-strong)] text-[var(--text-muted)]' : ''}`}
              >
                {isCompleted ? <Check className="h-4 w-4" /> : PHASE_ICONS[step.key]}
              </div>
              <span className={`text-xs whitespace-nowrap
                ${isActive ? 'font-medium text-[var(--accent-strong)]' : 'text-[var(--text-muted)]'}`}>
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
