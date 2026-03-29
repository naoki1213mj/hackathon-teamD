import { useState } from 'react'
import type { ApprovalRequest } from '../hooks/useSSE'
import { MarkdownView } from './MarkdownView'

interface PlanApprovalProps {
  request: ApprovalRequest
  onApprove: (response: string) => void
  t: (key: string) => string
}

export function PlanApproval({ request, onApprove, t }: PlanApprovalProps) {
  const [revision, setRevision] = useState('')
  const [mode, setMode] = useState<'view' | 'revise'>('view')

  return (
    <div className="space-y-4 rounded-[24px] border border-amber-200 bg-amber-50 p-5 dark:border-amber-900 dark:bg-amber-950/60">
      <h3 className="text-sm font-medium text-amber-800 dark:text-amber-300">
        ✅ {t('approval.title')}
      </h3>

      {request.plan_markdown && (
        <div className="rounded-[20px] bg-white p-4 dark:bg-gray-800">
          <MarkdownView content={request.plan_markdown} />
        </div>
      )}

      <p className="text-sm text-gray-700 dark:text-gray-300">{request.prompt}</p>

      {mode === 'view' ? (
        <div className="flex gap-3">
          <button
            onClick={() => setMode('revise')}
            type="button"
            className="rounded-full border border-gray-300 bg-white px-4 py-2 text-sm font-medium
                       text-gray-700 hover:bg-gray-50
                       dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
            autoFocus
          >
            {t('approval.revise')}
          </button>
          <button
            type="button"
            onClick={() => onApprove(t('approval.approve'))}
            className="rounded-full bg-green-600 px-4 py-2 text-sm font-medium text-white
                       hover:bg-green-700 dark:bg-green-500 dark:hover:bg-green-600"
          >
            {t('approval.approve')}
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <textarea
            value={revision}
            onChange={e => setRevision(e.target.value)}
            placeholder={t('approval.prompt')}
            rows={3}
            className="w-full resize-none rounded-[20px] border border-gray-200 bg-white px-3 py-2
                       text-sm focus:border-[var(--accent)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-soft)]
                       dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100"
            autoFocus
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setMode('view')}
              className="rounded-full border border-gray-300 px-3 py-1.5 text-sm text-gray-600
                         dark:border-gray-600 dark:text-gray-400"
            >
              {t('approval.back')}
            </button>
            <button
              type="button"
              onClick={() => { if (revision.trim()) onApprove(revision.trim()) }}
              disabled={!revision.trim()}
              className="rounded-full bg-[var(--accent)] px-3 py-1.5 text-sm text-white
                         hover:bg-blue-700 disabled:opacity-40
              "
            >
              {t('input.send')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
