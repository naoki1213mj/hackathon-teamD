import { useState, type FormEvent } from 'react'

interface RefineChatProps {
  onSubmit: (message: string) => void
  disabled: boolean
  placeholder: string
  sendLabel: string
  label: string
}

export function RefineChat({ onSubmit, disabled, placeholder, sendLabel, label }: RefineChatProps) {
  const [message, setMessage] = useState('')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!message.trim() || disabled) return
    onSubmit(message.trim())
    setMessage('')
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 pt-3 border-t border-[var(--panel-border)]">
      <label className="sr-only" htmlFor="refine-chat-message">{label}</label>
      <input
        id="refine-chat-message"
        type="text"
        value={message}
        onChange={e => setMessage(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        aria-label={label}
        className="flex-1 rounded-full border border-[var(--panel-border)] bg-[var(--panel-strong)] px-4 py-2.5 text-sm text-[var(--text-primary)]
                   placeholder:text-[var(--text-muted)] focus:border-[var(--accent)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-soft)]
                   disabled:opacity-50
        "
      />
      <button
        type="submit"
        disabled={disabled || !message.trim()}
        className="rounded-full bg-[var(--accent)] px-4 py-2 text-sm text-white
                   hover:opacity-90 disabled:opacity-40"
      >
        {sendLabel}
      </button>
    </form>
  )
}
