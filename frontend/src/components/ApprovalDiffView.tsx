import { buildTextDiff, summarizeTextDiff, type TextDiffLine, type TextDiffLineType } from '../lib/text-diff'

interface ApprovalDiffViewProps {
  previousText?: string
  currentText: string
  previousLabel?: string
  currentLabel?: string
  className?: string
  t: (key: string) => string
  variant?: 'unified' | 'side-by-side'
}

type SideBySideRowKind = 'unchanged' | 'changed' | 'removed' | 'added'

interface SideBySideDiffRow {
  kind: SideBySideRowKind
  previous?: TextDiffLine
  current?: TextDiffLine
}

const DIFF_STYLE: Record<TextDiffLineType, string> = {
  added: 'border-emerald-200 bg-emerald-50 text-emerald-950 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-100',
  removed: 'border-rose-200 bg-rose-50 text-rose-950 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-100',
  unchanged: 'border-[var(--panel-border)] bg-[var(--panel-bg)] text-[var(--text-secondary)]',
}

const EMPTY_CELL_STYLE = 'border-dashed border-[var(--panel-border)] bg-[var(--surface)] text-[var(--text-muted)] opacity-70'

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

function collectBlock(diffLines: TextDiffLine[], startIndex: number, type: TextDiffLineType) {
  const block: TextDiffLine[] = []
  let index = startIndex
  while (index < diffLines.length && diffLines[index].type === type) {
    block.push(diffLines[index])
    index += 1
  }
  return { block, nextIndex: index }
}

function buildSideBySideRows(diffLines: TextDiffLine[]): SideBySideDiffRow[] {
  const rows: SideBySideDiffRow[] = []
  let index = 0

  while (index < diffLines.length) {
    const line = diffLines[index]

    if (line.type === 'unchanged') {
      rows.push({ kind: 'unchanged', previous: line, current: line })
      index += 1
      continue
    }

    if (line.type === 'removed') {
      const removed = collectBlock(diffLines, index, 'removed')
      const added = collectBlock(diffLines, removed.nextIndex, 'added')
      const rowCount = Math.max(removed.block.length, added.block.length)

      for (let rowIndex = 0; rowIndex < rowCount; rowIndex += 1) {
        const previous = removed.block[rowIndex]
        const current = added.block[rowIndex]
        rows.push({
          kind: previous && current ? 'changed' : previous ? 'removed' : 'added',
          previous,
          current,
        })
      }

      index = added.nextIndex
      continue
    }

    const added = collectBlock(diffLines, index, 'added')
    for (const current of added.block) {
      rows.push({ kind: 'added', current })
    }
    index = added.nextIndex
  }

  return rows
}

function DiffCell({ line, side }: { line?: TextDiffLine, side: 'previous' | 'current' }) {
  const style = line ? DIFF_STYLE[line.type] : EMPTY_CELL_STYLE
  const symbol = line ? DIFF_SYMBOL[line.type] : side === 'previous' ? '−' : '+'

  return (
    <div
      data-diff-kind={line?.type ?? 'empty'}
      className={`grid min-h-9 grid-cols-[2rem_minmax(0,1fr)] gap-2 rounded-xl border px-2 py-1.5 text-xs leading-5 ${style}`}
    >
      <span className="select-none text-center font-mono font-semibold" aria-hidden="true">
        {symbol}
      </span>
      <code className="whitespace-pre-wrap break-words font-mono">
        {line?.text || ' '}
      </code>
    </div>
  )
}

export function ApprovalDiffView({
  previousText = '',
  currentText,
  previousLabel,
  currentLabel,
  className = '',
  t,
  variant = 'unified',
}: ApprovalDiffViewProps) {
  const diffLines = buildTextDiff(previousText, currentText)
  const summary = summarizeTextDiff(diffLines)
  const hasChanges = summary.added > 0 || summary.removed > 0
  const isSideBySide = variant === 'side-by-side'
  const sideBySideRows = isSideBySide ? buildSideBySideRows(diffLines) : []

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
        <div className="flex flex-wrap gap-1.5 text-[11px] font-medium" aria-hidden="true">
          <span className="rounded-full bg-rose-100 px-2 py-1 text-rose-800 dark:bg-rose-950/50 dark:text-rose-100">
            {t('approval.diff.removed')}
          </span>
          <span className="rounded-full bg-emerald-100 px-2 py-1 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-100">
            {t('approval.diff.added')}
          </span>
        </div>
      </div>

      {isSideBySide ? (
        <div className="max-h-[min(64vh,44rem)] overflow-auto rounded-2xl border border-[var(--panel-border)] bg-[var(--panel-bg)]">
          <div className="sticky top-0 z-10 grid border-b border-[var(--panel-border)] bg-[var(--panel-strong)] text-xs font-semibold text-[var(--text-secondary)] lg:grid-cols-2">
            <div className="border-b border-[var(--panel-border)] px-3 py-2 lg:border-b-0 lg:border-r">
              {previousLabel || t('approval.diff.previous')}
            </div>
            <div className="px-3 py-2">
              {currentLabel || t('approval.diff.current')}
            </div>
          </div>

          {sideBySideRows.length > 0 ? (
            <div className="space-y-1 p-2">
              {sideBySideRows.map((row, index) => (
                <div
                  key={`${row.kind}-${index}-${row.previous?.text ?? ''}-${row.current?.text ?? ''}`}
                  className="grid gap-1.5 lg:grid-cols-2"
                >
                  <DiffCell line={row.previous} side="previous" />
                  <DiffCell line={row.current} side="current" />
                </div>
              ))}
            </div>
          ) : (
            <p className="px-3 py-4 text-sm text-[var(--text-secondary)]">{t('approval.diff.no_changes')}</p>
          )}
        </div>
      ) : (
        <>
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
                  <DiffCell key={`${line.type}-${index}-${line.text}`} line={line} side={line.type === 'removed' ? 'previous' : 'current'} />
                ))}
              </div>
            ) : (
              <p className="px-2 py-3 text-sm text-[var(--text-secondary)]">{t('approval.diff.no_changes')}</p>
            )}
          </div>
        </>
      )}
    </section>
  )
}
