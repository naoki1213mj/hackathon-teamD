interface VersionSelectorProps {
  versions: number[]
  current: number
  onChange: (version: number) => void
  t: (key: string) => string
}

export function VersionSelector({ versions, current, onChange, t }: VersionSelectorProps) {
  if (versions.length <= 1) return null

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-[var(--text-muted)]">{t('version.label')}:</span>
      <div className="flex gap-1">
        {versions.map(v => (
          <button
            key={v}
            type="button"
            onClick={() => onChange(v)}
            className={`rounded-full px-2.5 py-1 text-xs font-medium
              ${v === current
                ? 'bg-[var(--accent-soft)] text-[var(--accent-strong)]'
                : 'bg-[var(--panel-strong)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              }`}
          >
            v{v}
          </button>
        ))}
      </div>
    </div>
  )
}
