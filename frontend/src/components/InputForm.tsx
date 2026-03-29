import { useState, type FormEvent } from 'react'

interface InputFormProps {
  onSubmit: (message: string) => void
  disabled: boolean
  placeholder: string
  sendLabel: string
  label: string
}

export function InputForm({ onSubmit, disabled, placeholder, sendLabel, label }: InputFormProps) {
  const [message, setMessage] = useState('')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!message.trim() || disabled) return
    onSubmit(message.trim())
    setMessage('')
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-3">
      <label className="sr-only" htmlFor="input-form-message">{label}</label>
      <textarea
        id="input-form-message"
        value={message}
        onChange={e => setMessage(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        rows={3}
        aria-label={label}
        className="flex-1 resize-none rounded-[24px] border border-[var(--panel-border)] bg-[var(--panel-strong)] px-4 py-3
                   text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)]
                   focus:border-[var(--accent)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-soft)]
                   disabled:opacity-50
        "
        onKeyDown={e => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSubmit(e)
          }
        }}
      />
      <button
        type="submit"
        disabled={disabled || !message.trim()}
        className="self-end rounded-full bg-[var(--accent)] px-6 py-3 text-sm font-medium text-white
                   hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-[var(--accent-soft)]
                   disabled:opacity-40 disabled:cursor-not-allowed
        "
      >
        {sendLabel}
      </button>
    </form>
  )
}
