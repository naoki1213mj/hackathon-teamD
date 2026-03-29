import { useState, type ReactNode } from 'react'

interface Tab {
  key: string
  label: string
  content: ReactNode
}

interface ArtifactTabsProps {
  tabs: Tab[]
  t: (key: string) => string
}

export function ArtifactTabs({ tabs, t }: ArtifactTabsProps) {
  const [activeTab, setActiveTab] = useState(tabs[0]?.key || '')

  const activeTabs = tabs.filter(tab => tab.content !== null)

  if (activeTabs.length === 0) return null

  const effectiveActiveTab = activeTabs.some(tab => tab.key === activeTab) ? activeTab : activeTabs[0].key
  const currentTab = activeTabs.find(tab => tab.key === effectiveActiveTab) || activeTabs[0]

  return (
    <div className="flex min-h-[0] flex-1 flex-col">
      <div className="flex flex-wrap gap-2 border-b border-[var(--panel-border)] pb-3" role="tablist" aria-label={t('panel.preview')}>
        {activeTabs.map(tab => (
          <button
            key={tab.key}
            id={`artifact-tab-${tab.key}`}
            type="button"
            role="tab"
            data-selected={effectiveActiveTab === tab.key ? 'true' : 'false'}
            aria-controls={`artifact-panel-${tab.key}`}
            onClick={() => setActiveTab(tab.key)}
            className={`rounded-full px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]
              ${effectiveActiveTab === tab.key
                ? 'bg-[var(--accent-soft)] text-[var(--accent-strong)]'
                : 'bg-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div
        id={`artifact-panel-${currentTab.key}`}
        role="tabpanel"
        aria-labelledby={`artifact-tab-${currentTab.key}`}
        className="min-h-[0] flex-1 py-4"
      >
        {currentTab.content || (
          <div className="rounded-3xl border border-dashed border-[var(--panel-border)] px-6 py-10 text-sm text-[var(--text-muted)]">
            {t('preview.unavailable')}
          </div>
        )}
      </div>
    </div>
  )
}
