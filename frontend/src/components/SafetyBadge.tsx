import { AlertTriangle, CheckCircle, HelpCircle } from 'lucide-react'
import type { SafetyResult } from '../hooks/useSSE'

interface SafetyBadgeProps {
  result: SafetyResult | null
  t: (key: string) => string
}

export function SafetyBadge({ result, t }: SafetyBadgeProps) {
  if (!result) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-[var(--panel-border)] bg-[var(--panel-strong)] px-3 py-2 text-xs text-[var(--text-muted)]">
        <span className="h-2 w-2 rounded-full bg-slate-400" />
        {t('safety.checking')}
      </span>
    )
  }

  const isSafe = result.status === 'safe'
  const isError = result.status === 'error'

  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs
      ${isSafe
        ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-300'
        : isError
          ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-300'
          : 'border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-300'
      }`}
    >
      <span>{isSafe ? <CheckCircle className="h-3.5 w-3.5" /> : isError ? <HelpCircle className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}</span>
      <span>{isSafe ? t('safety.safe') : isError ? t('safety.error') : t('safety.warning')}</span>
    </span>
  )
}
