import { Check, Copy, ExternalLink } from 'lucide-react'
import { useState } from 'react'

interface ManagerApprovalStatusProps {
  request: {
    prompt: string
    manager_email?: string
    manager_approval_url?: string
    manager_delivery_mode?: 'manual' | 'workflow'
  }
  t: (key: string) => string
}

export function ManagerApprovalStatus({ request, t }: ManagerApprovalStatusProps) {
  const [isCopied, setIsCopied] = useState(false)
  const prompt = request.prompt.trim() || t('approval.manager.awaiting_action').replace('{email}', request.manager_email || 'manager')
  const isManualDelivery = request.manager_delivery_mode === 'manual' && request.manager_approval_url

  const copyApprovalUrl = async () => {
    if (!request.manager_approval_url) return
    try {
      await navigator.clipboard.writeText(request.manager_approval_url)
      setIsCopied(true)
      window.setTimeout(() => setIsCopied(false), 2000)
    } catch {
      setIsCopied(false)
    }
  }

  return (
    <div className="sticky bottom-0 z-30 mx-0 mt-2 rounded-2xl border border-indigo-200 bg-indigo-50/95 px-6 py-5 shadow-[0_-4px_30px_rgba(99,102,241,0.12)] backdrop-blur-lg dark:border-indigo-900/60 dark:bg-slate-900/95">
      <div className="flex items-start gap-3">
        <span className="mt-1 relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-indigo-500" />
        </span>
        <div>
          <h3 className="text-sm font-semibold text-indigo-900 dark:text-indigo-100">{t('approval.title')}</h3>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">{prompt}</p>
          {request.manager_email && (
            <p className="mt-2 text-xs text-[var(--text-muted)]">
              {t('settings.manager.email')}: {request.manager_email}
            </p>
          )}
          {isManualDelivery && (
            <div className="mt-4 rounded-2xl border border-indigo-200/80 bg-white/70 px-4 py-4 dark:border-indigo-800/60 dark:bg-slate-950/40">
              <p className="text-xs leading-5 text-[var(--text-secondary)]">{t('approval.manager.manual_share')}</p>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <a
                  href={request.manager_approval_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-700"
                >
                  <ExternalLink className="h-4 w-4" />
                  {t('approval.manager.open_link')}
                </a>
                <button
                  type="button"
                  onClick={() => { void copyApprovalUrl() }}
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-indigo-300 px-4 py-2 text-sm font-medium text-indigo-900 transition-colors hover:bg-indigo-100 dark:border-indigo-700 dark:text-indigo-100 dark:hover:bg-indigo-900/40"
                >
                  {isCopied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  {isCopied ? t('approval.manager.copied') : t('approval.manager.copy_link')}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
