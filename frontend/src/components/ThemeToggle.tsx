import type { Theme } from '../hooks/useTheme';

interface ThemeToggleProps {
  theme: Theme
  onChange: (theme: Theme) => void
  t: (key: string) => string
}

const THEMES: { value: Theme; icon: string; labelKey: string }[] = [
  { value: 'light', icon: '☀', labelKey: 'theme.light' },
  { value: 'dark', icon: '◐', labelKey: 'theme.dark' },
  { value: 'system', icon: '⌘', labelKey: 'theme.system' },
]

export function ThemeToggle({ theme, onChange, t }: ThemeToggleProps) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-[var(--panel-border)] bg-[var(--panel-strong)] px-1 py-1">
      <span className="px-2 text-[11px] font-medium uppercase tracking-[0.18em] text-[var(--text-muted)]">
        {t('theme.label')}
      </span>
      {THEMES.map(option => (
        <button
          key={option.value}
          onClick={() => onChange(option.value)}
          type="button"
          data-active={theme === option.value ? 'true' : 'false'}
          className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]
            ${theme === option.value
              ? 'bg-[var(--accent-soft)] text-[var(--accent-strong)]'
              : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }
          `}
          title={t(option.labelKey)}
        >
          <span aria-hidden="true">{option.icon}</span>
          <span>{t(option.labelKey)}</span>
        </button>
      ))}
    </div>
  )
}
