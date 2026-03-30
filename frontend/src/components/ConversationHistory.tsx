/**
 * 会話履歴サイドバー。右からスライドインするドロワー。
 */

import { useState, useEffect, useCallback } from 'react'

interface Conversation {
  id: string
  input: string
  status: string
  created_at: string
}

interface ConversationHistoryProps {
  onSelect: (conversationId: string) => void
  t: (key: string) => string
}

export function ConversationHistory({ onSelect, t }: ConversationHistoryProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(false)

  const fetchHistory = useCallback(async () => {
    setLoading(true)
    try {
      const resp = await fetch('/api/conversations')
      const data = await resp.json()
      setConversations(data.conversations || [])
    } catch {
      setConversations([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isOpen) fetchHistory()
  }, [isOpen, fetchHistory])

  const handleSelect = (id: string) => {
    onSelect(id)
    setIsOpen(false)
  }

  const formatTime = (dateStr: string) => {
    try {
      const date = new Date(dateStr)
      const now = new Date()
      const diff = now.getTime() - date.getTime()
      const minutes = Math.floor(diff / 60000)
      if (minutes < 60) return `${minutes}分前`
      const hours = Math.floor(minutes / 60)
      if (hours < 24) return `${hours}時間前`
      return date.toLocaleDateString('ja-JP', { month: 'short', day: 'numeric' })
    } catch {
      return dateStr
    }
  }

  const statusIcon = (status: string) => {
    switch (status) {
      case 'completed': return '✅'
      case 'awaiting_approval': return '⏳'
      case 'error': return '❌'
      default: return '🔄'
    }
  }

  return (
    <>
      {/* トリガーボタン */}
      <button
        onClick={() => setIsOpen(true)}
        className="rounded-full border border-[var(--panel-border)] bg-[var(--surface)] p-2 text-[var(--text-secondary)] transition-colors hover:bg-[var(--accent-soft)] hover:text-[var(--text-primary)]"
        title={t('history.title')}
        aria-label={t('history.title')}
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </button>

      {/* バックドロップ */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[2px] transition-opacity"
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* サイドバーパネル */}
      <div
        className={`fixed right-0 top-0 z-50 h-full w-full sm:w-96 transform transition-transform duration-300 ease-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex h-full flex-col border-l border-[var(--panel-border)] bg-[var(--panel-bg)] shadow-2xl backdrop-blur-xl">
          {/* ヘッダー */}
          <div className="flex items-center justify-between border-b border-[var(--panel-border)] px-5 py-4">
            <div className="flex items-center gap-2">
              <svg className="h-5 w-5 text-[var(--accent)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <h2 className="text-base font-semibold">{t('history.title')}</h2>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="rounded-lg p-1.5 text-[var(--text-muted)] hover:bg-[var(--accent-soft)] hover:text-[var(--text-primary)] transition-colors"
              aria-label="Close"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* コンテンツ */}
          <div className="flex-1 overflow-y-auto px-4 py-3">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--accent)] border-t-transparent" />
              </div>
            ) : conversations.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-[var(--text-muted)]">
                <svg className="mb-3 h-12 w-12 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <p className="text-sm">{t('history.empty')}</p>
              </div>
            ) : (
              <div className="space-y-2">
                {conversations.map((conv) => (
                  <button
                    key={conv.id}
                    onClick={() => handleSelect(conv.id)}
                    className="group w-full rounded-xl border border-[var(--panel-border)] bg-[var(--surface)] p-4 text-left transition-all hover:border-[var(--accent)] hover:shadow-md"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="flex-1 text-sm font-medium leading-snug line-clamp-2 group-hover:text-[var(--accent-strong)]">
                        {conv.input || '(入力なし)'}
                      </p>
                      <span className="shrink-0 text-base" title={conv.status}>
                        {statusIcon(conv.status)}
                      </span>
                    </div>
                    <div className="mt-2 flex items-center gap-2 text-xs text-[var(--text-muted)]">
                      <span>{formatTime(conv.created_at)}</span>
                      <span>•</span>
                      <span className="font-mono">{conv.id.slice(0, 8)}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* フッター */}
          <div className="border-t border-[var(--panel-border)] px-5 py-3">
            <p className="text-center text-xs text-[var(--text-muted)]">
              {conversations.length} {conversations.length === 1 ? 'conversation' : 'conversations'}
            </p>
          </div>
        </div>
      </div>
    </>
  )
}
