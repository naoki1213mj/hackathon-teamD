import { buildTextDiff, summarizeTextDiff, type TextDiffLineType } from '../lib/text-diff'

interface ApprovalDiffViewProps {
  previousText?: string
  currentText: string
  previousLabel?: string
  currentLabel?: string
  className?: string
  t: (key: string) => string
}

const DIFF_STYLE: Record<TextDiffLineType, string> = {
  added: 'border-emerald-200 bg-emerald-50 text-emerald-950 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-100',
  removed: 'border-rose-200 bg-rose-50 text-rose-950 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-100',
  unchanged: 'border-[var(--panel-border)] bg-[var(--panel-bg)] text-[var(--text-secondary)]',
}

const DIFF_SYMBOL: Record<TextDiffLineType, string> = {
  added: '+',
  removed: '−',
  unchanged: ' ',
}

function formatSummary(template: string, added: number, removed: number, unchanged: number): string {
  return template
    .replace('{added}', String(added))
    .replace('{removed}', String(removed))
    .replace('{unchanged}', String(unchanged))
}

export function ApprovalDiffView({
  previousText = '',
  currentText,
  previousLabel,
  currentLabel,
  className = '',
  t,
}: ApprovalDiffViewProps) {
  const diffLines = buildTextDiff(previousText, currentText)
  const summary = summarizeTextDiff(diffLines)
  const hasChanges = summary.added > 0 || summary.removed > 0

  return (
    <section
      className={[
        'space-y-3 rounded-[20px] border border-[var(--panel-border)] bg-[var(--panel-strong)] p-4',
        className,
      ].join(' ')}
      aria-label={t('approval.diff.title')}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-[var(--text-primary)]">{t('approval.diff.title')}</h4>
          <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
            {hasChanges
              ? formatSummary(t('approval.diff.summary'), summary.added, summary.removed, summary.unchanged)
              : t('approval.diff.no_changes')}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5 text-[11px] font-medium">
          <span className="rounded-full bg-rose-100 px-2 py-1 text-rose-800 dark:bg-rose-950/50 dark:text-rose-100">
            {t('approval.diff.removed')}
          </span>
          <span className="rounded-full bg-emerald-100 px-2 py-1 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-100">
            {t('approval.diff.added')}
          </span>
        </div>
      </div>

      {(previousLabel || currentLabel) && (
        <div className="grid gap-2 text-xs text-[var(--text-muted)] sm:grid-cols-2">
          <p>{previousLabel || t('approval.diff.previous')}</p>
          <p>{currentLabel || t('approval.diff.current')}</p>
        </div>
      )}

      <div className="max-h-80 overflow-auto rounded-2xl border border-[var(--panel-border)] bg-[var(--panel-bg)] p-2">
        {diffLines.length > 0 ? (
          <div className="space-y-1">
            {diffLines.map((line, index) => (
              <div
                key={`${line.type}-${index}-${line.text}`}
                data-diff-kind={line.type}
                className={`grid grid-cols-[2rem_minmax(0,1fr)] gap-2 rounded-xl border px-2 py-1.5 text-xs leading-5 ${DIFF_STYLE[line.type]}`}
              >
                <span className="select-none text-center font-mono font-semibold" aria-hidden="true">
                  {DIFF_SYMBOL[line.type]}
                </span>
                <code className="whitespace-pre-wrap break-words font-mono">
                  {line.text || ' '}
                </code>
              </div>
            ))}
          </div>
        ) : (
          <p className="px-2 py-3 text-sm text-[var(--text-secondary)]">{t('approval.diff.no_changes')}</p>
        )}
      </div>
    </section>
  )
}
