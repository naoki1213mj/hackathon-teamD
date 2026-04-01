import { useEffect, useState, type ReactNode } from 'react'
import { FileText, Image, Layout, Video } from 'lucide-react'

interface Tab {
  key: string
  label: string
  content: ReactNode
}

interface ArtifactTabsProps {
  tabs: Tab[]
  t: (key: string) => string
  activeAgent?: string
}

const TAB_ICONS: Record<string, React.ReactNode> = {
  plan: <FileText className="h-3.5 w-3.5" />,
  brochure: <Layout className="h-3.5 w-3.5" />,
  images: <Image className="h-3.5 w-3.5" />,
  video: <Video className="h-3.5 w-3.5" />,
}

export function ArtifactTabs({ tabs, t, activeAgent }: ArtifactTabsProps) {
  const [activeTab, setActiveTab] = useState(tabs[0]?.key || '')

  // エージェント進捗に応じてタブを自動切替
  useEffect(() => {
    if (!activeAgent) return
    const agentTabMap: Record<string, string> = {
      'marketing-plan-agent': 'plan',
      'plan-revision-agent': 'plan',
      'regulation-check-agent': 'plan',
      'brochure-gen-agent': 'brochure',
      'video-gen-agent': 'video',
    }
    const tab = agentTabMap[activeAgent]
    if (tab) setActiveTab(tab)
  }, [activeAgent])

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
            className={`inline-flex items-center rounded-full px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]
              ${effectiveActiveTab === tab.key
                ? 'bg-[var(--accent-soft)] text-[var(--accent-strong)]'
                : 'bg-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              }`}
          >
            {TAB_ICONS[tab.key] && <span className="mr-1.5">{TAB_ICONS[tab.key]}</span>}
            {tab.label}
          </button>
        ))}
      </div>
      <div
        key={currentTab.key}
        id={`artifact-panel-${currentTab.key}`}
        role="tabpanel"
        aria-labelledby={`artifact-tab-${currentTab.key}`}
        className="min-h-[0] flex-1 py-4 animate-fade-slide-in"
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
