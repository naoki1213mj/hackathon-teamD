import { useCallback, useState } from 'react'

interface VoiceInputProps {
  disabled?: boolean
  t: (key: string) => string
}

export function VoiceInput({ disabled = false, t }: VoiceInputProps) {
  const [isOpen, setIsOpen] = useState(false)

  const togglePreview = useCallback(() => {
    setIsOpen(prev => !prev)
  }, [])

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={togglePreview}
        disabled={disabled}
        className={`inline-flex items-center justify-center rounded-full border border-[var(--panel-border)] bg-[var(--panel-strong)] p-2.5 text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] ${disabled ? 'cursor-not-allowed opacity-50' : ''}`}
        aria-label={t('voice.button')}
        title={t('voice.label')}
      >
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
        </svg>
      </button>
      {isOpen && (
        <span className="max-w-56 rounded-full bg-[var(--accent-soft)] px-3 py-1 text-xs text-[var(--accent-strong)]">
          {t('voice.preview')}
        </span>
      )}
    </div>
  )
}
