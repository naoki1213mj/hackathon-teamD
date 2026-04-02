import { CheckCircle, ExternalLink, MessageSquare, Search, Sparkles, XCircle } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { ArtifactSnapshot } from '../hooks/useSSE'
import {
    calculateEvaluationOverall,
    getLatestEvaluation,
    hasBuiltinMetrics,
    type EvaluationRecord,
    type EvaluationResult,
} from '../lib/evaluation'

interface EvaluationPanelProps {
  query: string
  response: string
  html: string
  t: (key: string) => string
  conversationId?: string | null
  artifactVersion?: number
  evaluations?: EvaluationRecord[]
  versions?: ArtifactSnapshot[]
  isLatestVersion?: boolean
  onSelectVersion?: (version: number) => void
  onEvaluationRecorded?: (record: EvaluationRecord) => void
  onRefine?: (feedback: string) => void
}

function ScoreBadge({ score, max = 5 }: { score: number; max?: number }) {
  if (score < 0) return <span className="text-xs text-[var(--text-muted)]">N/A</span>
  const pct = (score / max) * 100
  const color = pct >= 80 ? 'text-green-500' : pct >= 60 ? 'text-yellow-500' : 'text-red-500'
  return (
    <span className={`text-sm font-bold ${color}`}>
      {score.toFixed(1)}<span className="text-xs font-normal text-[var(--text-muted)]">/{max}</span>
    </span>
  )
}

function CheckItem({ label, passed }: { label: string; passed: boolean }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs">
      <span>{passed ? <CheckCircle className="h-3.5 w-3.5 text-green-500" /> : <XCircle className="h-3.5 w-3.5 text-red-400" />}</span>
      <span className={passed ? 'text-[var(--text-secondary)]' : 'text-red-400'}>{label}</span>
    </span>
  )
}

function ScoreDelta({ current, previous }: { current: number; previous: number }) {
  if (current < 0 || previous < 0) return null
  const delta = current - previous
  if (Math.abs(delta) < 0.05) return null
  const isUp = delta > 0
  return (
    <span className={`ml-1 text-[10px] font-medium ${isUp ? 'text-green-500' : 'text-red-400'}`}>
      {isUp ? '▲' : '▼'} {Math.abs(delta).toFixed(1)}
    </span>
  )
}

function buildFeedback(result: EvaluationResult, t: (key: string) => string): string {
  const issues: string[] = []

  if (hasBuiltinMetrics(result.builtin)) {
    for (const [name, val] of Object.entries(result.builtin)) {
      if (val.score >= 0 && val.score < 3) {
        issues.push(`${t(`eval.${name}`) || name}が低い（${val.score}/5）${val.reason ? ': ' + val.reason : ''}`)
      }
    }
  }

  if (result.marketing_quality) {
    for (const key of ['appeal', 'differentiation', 'kpi_validity', 'brand_tone']) {
      const val = result.marketing_quality[key]
      if (typeof val === 'number' && val < 3) {
        issues.push(`${t(`eval.${key}`) || key}が低い（${val}/5）`)
      }
    }
    if (result.marketing_quality.reason) {
      issues.push(`審査コメント: ${String(result.marketing_quality.reason)}`)
    }
  }

  if (result.custom) {
    for (const [name, val] of Object.entries(result.custom)) {
      if (!val.details) continue
      const missing = Object.entries(val.details)
        .filter(([, passed]) => !passed)
        .map(([item]) => item)
      if (missing.length > 0) {
        issues.push(`${t(`eval.${name}`) || name}: ${missing.join('・')}が不足`)
      }
    }
  }

  if (issues.length === 0) {
    return '品質評価の結果、全項目が基準を満たしています。さらにクオリティを高めてください。'
  }

  return `以下の品質評価結果に基づいて企画書を改善してください:\n${issues.map(item => `- ${item}`).join('\n')}`
}

export function EvaluationPanel({
  query,
  response,
  html,
  t,
  conversationId,
  artifactVersion,
  evaluations = [],
  versions = [],
  isLatestVersion = true,
  onSelectVersion,
  onEvaluationRecorded,
  onRefine,
}: EvaluationPanelProps) {
  const [draftHistories, setDraftHistories] = useState<Record<string, EvaluationRecord[]>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const evaluationKey = useMemo(
    () => JSON.stringify([conversationId ?? 'draft', artifactVersion ?? 0, query, response]),
    [artifactVersion, conversationId, query, response],
  )
  const history = artifactVersion && artifactVersion > 0
    ? evaluations
    : (draftHistories[evaluationKey] ?? [])

  const latestRecord = getLatestEvaluation(history)
  const previousRecord = history.length > 1 ? history[history.length - 2] : null
  const result = latestRecord?.result ?? null
  const previousResult = previousRecord?.result ?? null
  const previousBuiltin = previousResult && hasBuiltinMetrics(previousResult.builtin) ? previousResult.builtin : undefined
  const versionComparisons = versions
    .map((snapshot, index) => {
      const latest = getLatestEvaluation(snapshot.evaluations)
      if (!latest) return null
      return {
        version: index + 1,
        latest,
        overall: calculateEvaluationOverall(latest.result),
      }
    })
    .filter((item): item is { version: number; latest: EvaluationRecord; overall: number } => item !== null)

  const runEvaluation = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          response,
          html,
          conversation_id: conversationId,
          artifact_version: artifactVersion,
        }),
      })
      if (!res.ok) {
        setError(`HTTP ${res.status}`)
        return
      }

      const data = await res.json() as EvaluationResult & {
        evaluation_meta?: { version: number; round: number; created_at: string } | null
      }
      const record: EvaluationRecord = {
        version: data.evaluation_meta?.version ?? artifactVersion ?? 1,
        round: data.evaluation_meta?.round ?? (history.length + 1),
        createdAt: data.evaluation_meta?.created_at ?? new Date().toISOString(),
        result: {
          builtin: data.builtin,
          custom: data.custom,
          marketing_quality: data.marketing_quality,
          foundry_portal_url: data.foundry_portal_url,
          error: data.error,
        },
      }

      if (artifactVersion && artifactVersion > 0) {
        onEvaluationRecorded?.(record)
      } else {
        setDraftHistories(prev => ({
          ...prev,
          [evaluationKey]: [...(prev[evaluationKey] ?? []), record],
        }))
      }
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  if (!response) return null

  return (
    <div className="mt-4 space-y-3">
      <div className="flex items-center gap-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          {t('eval.title')}
        </h4>
        <button
          onClick={runEvaluation}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-full bg-[var(--accent-soft)] px-3 py-1.5 text-xs font-medium text-[var(--accent-strong)] transition-colors hover:bg-[var(--accent)]/20 disabled:opacity-40"
        >
          {loading ? (
            <>
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--accent)] border-t-transparent" />
              {t('eval.running')}
            </>
          ) : (
            <><Search className="h-3.5 w-3.5" /> {t('eval.run')}</>
          )}
        </button>
      </div>

      {error && (
        <p className="inline-flex items-center gap-1 text-xs text-red-500"><XCircle className="h-3.5 w-3.5" /> {error}</p>
      )}

      {result && (
        <div className="space-y-3 rounded-2xl border border-[var(--panel-border)] bg-[var(--panel-strong)] p-4">
          {versionComparisons.length > 1 && (
            <div>
              <p className="mb-2 text-xs font-medium text-[var(--text-secondary)]">{t('eval.compare')}</p>
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {versionComparisons.map(item => {
                  const previousVersion = versionComparisons.find(candidate => candidate.version === item.version - 1)
                  return (
                    <button
                      key={item.version}
                      type="button"
                      disabled={!onSelectVersion}
                      onClick={() => onSelectVersion?.(item.version)}
                      className={`rounded-2xl border px-3 py-3 text-left transition-colors ${
                        item.version === artifactVersion
                          ? 'border-[var(--accent)] bg-[var(--accent-soft)]'
                          : 'border-[var(--panel-border)] bg-[var(--panel-bg)] hover:border-[var(--accent)]/40 disabled:hover:border-[var(--panel-border)]'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--text-muted)]">v{item.version}</p>
                          <p className="mt-1 text-xs font-medium text-[var(--text-secondary)]">
                            {t('eval.round').replace('{n}', String(item.latest.round))}
                          </p>
                        </div>
                        <div className="text-right">
                          <ScoreBadge score={item.overall} />
                          {previousVersion && <ScoreDelta current={item.overall} previous={previousVersion.overall} />}
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {latestRecord && (
            <p className="text-[10px] font-medium text-[var(--text-muted)]">
              {t('eval.round').replace('{n}', String(latestRecord.round))}
            </p>
          )}

          {hasBuiltinMetrics(result.builtin) && (
            <div>
              <p className="mb-2 text-xs font-medium text-[var(--text-secondary)]">{t('eval.builtin')}</p>
              <div className="flex flex-wrap gap-4">
                {Object.entries(result.builtin).map(([name, val]) => (
                  <div key={name} className="text-center">
                    <ScoreBadge score={val.score} />
                    {previousBuiltin?.[name] != null && (
                      <ScoreDelta current={val.score} previous={previousBuiltin[name].score} />
                    )}
                    <p className="mt-0.5 text-[10px] text-[var(--text-muted)]">{t(`eval.${name}`) || name}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.marketing_quality && !('score' in result.marketing_quality && result.marketing_quality.score === -1) && (
            <div>
              <p className="mb-2 text-xs font-medium text-[var(--text-secondary)]">{t('eval.marketing')}</p>
              <div className="flex flex-wrap gap-4">
                {['appeal', 'differentiation', 'kpi_validity', 'brand_tone', 'overall'].map(key => {
                  const val = result.marketing_quality?.[key]
                  const prevVal = previousResult?.marketing_quality?.[key]
                  return typeof val === 'number' ? (
                    <div key={key} className="text-center">
                      <ScoreBadge score={val} />
                      {typeof prevVal === 'number' && <ScoreDelta current={val} previous={prevVal} />}
                      <p className="mt-0.5 text-[10px] text-[var(--text-muted)]">{t(`eval.${key}`) || key}</p>
                    </div>
                  ) : null
                })}
              </div>
              {result.marketing_quality.reason && (
                <p className="mt-1 inline-flex items-center gap-1 text-xs text-[var(--text-secondary)]"><MessageSquare className="h-3 w-3" /> {String(result.marketing_quality.reason)}</p>
              )}
            </div>
          )}

          {result.custom && (
            <div>
              <p className="mb-2 text-xs font-medium text-[var(--text-secondary)]">{t('eval.compliance')}</p>
              <div className="space-y-2">
                {Object.entries(result.custom).map(([name, val]) => (
                  <div key={name}>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-[var(--text-secondary)]">{t(`eval.${name}`) || name}</span>
                      <ScoreBadge score={val.score} max={1} />
                    </div>
                    {val.details && (
                      <div className="mt-1 flex flex-wrap gap-2">
                        {Object.entries(val.details).map(([item, passed]) => (
                          <CheckItem key={item} label={item} passed={passed as boolean} />
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.foundry_portal_url && (
            <a
              href={result.foundry_portal_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-[var(--accent-strong)] hover:underline"
            >
              <ExternalLink className="h-3.5 w-3.5" /> {t('eval.portal')}
            </a>
          )}

          {onRefine && result && isLatestVersion && (
            <button
              onClick={() => {
                const feedback = buildFeedback(result, t)
                if (feedback) {
                  onRefine(feedback)
                }
              }}
              className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-full border border-[var(--accent)] bg-[var(--accent-soft)] px-4 py-2 text-xs font-medium text-[var(--accent-strong)] transition-colors hover:bg-[var(--accent)]/20"
            >
              <Sparkles className="h-3.5 w-3.5" /> {t('eval.refine')}
            </button>
          )}

          {onRefine && result && !isLatestVersion && (
            <p className="text-xs text-[var(--text-muted)]">{t('eval.refine.latest_only')}</p>
          )}
        </div>
      )}

      {!result && versionComparisons.length > 0 && artifactVersion && artifactVersion > 0 && (
        <div className="rounded-2xl border border-dashed border-[var(--panel-border)] bg-[var(--panel-strong)] px-4 py-3 text-xs text-[var(--text-muted)]">
          {t('eval.no_result')}
        </div>
      )}
    </div>
  )
}
