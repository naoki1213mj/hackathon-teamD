import { useState } from 'react';

interface EvaluationResult {
  builtin?: Record<string, { score: number; reason?: string }>
  custom?: Record<string, { score: number; details?: Record<string, boolean>; reason?: string }>
  marketing_quality?: Record<string, number | string>
  foundry_portal_url?: string
  error?: string
}

interface EvaluationPanelProps {
  query: string
  response: string
  html: string
  t: (key: string) => string
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
      <span>{passed ? '✅' : '❌'}</span>
      <span className={passed ? 'text-[var(--text-secondary)]' : 'text-red-400'}>{label}</span>
    </span>
  )
}

export function EvaluationPanel({ query, response, html, t }: EvaluationPanelProps) {
  const [result, setResult] = useState<EvaluationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runEvaluation = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, response: response.slice(0, 5000), html: html.slice(0, 5000) }),
      })
      if (!res.ok) {
        setError(`HTTP ${res.status}`)
        return
      }
      setResult(await res.json() as EvaluationResult)
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  if (!response) return null

  return (
    <div className="mt-4 space-y-3">
      <div className="flex items-center justify-between">
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
            <>🔍 {t('eval.run')}</>
          )}
        </button>
      </div>

      {error && (
        <p className="text-xs text-red-500">❌ {error}</p>
      )}

      {result && (
        <div className="space-y-3 rounded-2xl border border-[var(--panel-border)] bg-[var(--panel-strong)] p-4">
          {/* Built-in 評価器 */}
          {result.builtin && !('error' in result.builtin) && (
            <div>
              <p className="mb-2 text-xs font-medium text-[var(--text-secondary)]">{t('eval.builtin')}</p>
              <div className="flex flex-wrap gap-4">
                {Object.entries(result.builtin).map(([name, val]) => (
                  <div key={name} className="text-center">
                    <ScoreBadge score={val.score} />
                    <p className="mt-0.5 text-[10px] text-[var(--text-muted)]">{t(`eval.${name}`) || name}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* カスタム: 企画書品質（Prompt-based LLM ジャッジ） */}
          {result.marketing_quality && !('score' in result.marketing_quality && result.marketing_quality.score === -1) && (
            <div>
              <p className="mb-2 text-xs font-medium text-[var(--text-secondary)]">{t('eval.marketing')}</p>
              <div className="flex flex-wrap gap-4">
                {['target_clarity', 'differentiation', 'kpi_validity', 'creativity', 'overall'].map(key => {
                  const val = result.marketing_quality?.[key]
                  return typeof val === 'number' ? (
                    <div key={key} className="text-center">
                      <ScoreBadge score={val} />
                      <p className="mt-0.5 text-[10px] text-[var(--text-muted)]">{t(`eval.${key}`) || key}</p>
                    </div>
                  ) : null
                })}
              </div>
              {result.marketing_quality.reason && (
                <p className="mt-1 text-xs text-[var(--text-secondary)]">💬 {String(result.marketing_quality.reason)}</p>
              )}
            </div>
          )}

          {/* カスタム: Code-based チェック */}
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

          {/* Foundry ポータルリンク */}
          {result.foundry_portal_url && (
            <a
              href={result.foundry_portal_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-[var(--accent-strong)] hover:underline"
            >
              📊 {t('eval.portal')} →
            </a>
          )}
        </div>
      )}
    </div>
  )
}
