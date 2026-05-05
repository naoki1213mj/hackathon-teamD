import { cleanup, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DEFAULT_WORKIQ_SOURCE_SCOPE, type WorkIqUiStatus } from './SettingsPanel'
import { WorkIqSourceStatus } from './WorkIqSourceStatus'

const translations: Record<string, string> = {
  'settings.workiq.source.meeting_notes': '会議メモ',
  'settings.workiq.source.emails': 'メール',
  'settings.workiq.source.teams_chats': 'Teams チャット',
  'settings.workiq.source.documents_notes': 'ドキュメント/ノート',
  'settings.workiq.sourceStatus.title': 'ソース別ステータス',
  'settings.workiq.sourceStatus.safeOnly': '要約のみ表示',
  'settings.workiq.sourceStatus.summary': 'サニタイズ済みプレビュー',
  'settings.workiq.sourceStatus.off': 'オフ',
  'settings.workiq.sourceStatus.ready': '確認待ち',
  'settings.workiq.sourceStatus.sign_in_required': 'サインイン',
  'settings.workiq.sourceStatus.consent_required': '同意が必要',
  'settings.workiq.sourceStatus.unavailable': '利用不可',
  'settings.workiq.sourceStatus.used': '使用済み',
  'settings.workiq.sourceStatus.connector_used': 'コネクタ実行',
  'settings.workiq.sourceStatus.count': '{count} 件',
  'settings.workiq.sourceStatus.noPreview': '表示できるサニタイズ済みプレビューはまだありません。',
}

function t(key: string): string {
  return translations[key] ?? key
}

function renderStatus(status: WorkIqUiStatus, enabled = true) {
  render(
    <WorkIqSourceStatus
      enabled={enabled}
      selectedSources={DEFAULT_WORKIQ_SOURCE_SCOPE}
      status={status}
      t={t}
    />,
  )
}

describe('WorkIqSourceStatus', () => {
  it('shows all sources as off when Work IQ is disabled', () => {
    renderStatus('off', false)

    expect(screen.getAllByText('オフ')).toHaveLength(4)
  })

  it('shows source-level sign-in, consent, unavailable, and ready states', () => {
    renderStatus('sign_in_required')
    expect(screen.getAllByText('サインイン')).toHaveLength(4)

    cleanup()
    renderStatus('consent_required')
    expect(screen.getAllByText('同意が必要')).toHaveLength(4)

    cleanup()
    renderStatus('unavailable')
    expect(screen.getAllByText('利用不可')).toHaveLength(4)

    cleanup()
    renderStatus('ready')
    expect(screen.getAllByText('確認待ち')).toHaveLength(4)
  })

  it('uses sanitized source metadata previews without raw workplace content fields', () => {
    render(
      <WorkIqSourceStatus
        enabled
        selectedSources={['emails']}
        status="enabled"
        sourceMetadata={[{
          source: 'emails',
          label: 'メール',
          count: 3,
          status: 'completed',
          preview: 'メールでは上質感重視の方針です。',
        }]}
        t={t}
      />,
    )

    expect(screen.getByText('使用済み')).toBeInTheDocument()
    expect(screen.getByText('3 件')).toBeInTheDocument()
    expect(screen.getByText('メールでは上質感重視の方針です。')).toBeInTheDocument()
    expect(screen.getAllByText('オフ')).toHaveLength(3)
  })

  it('hides the entire panel when foundry MCP returns only connector_used markers without count or preview', () => {
    const { container } = render(
      <WorkIqSourceStatus
        enabled
        selectedSources={['meeting_notes', 'emails', 'teams_chats', 'documents_notes']}
        status="enabled"
        sourceMetadata={[
          { source: 'meeting_notes', status: 'connector_used' },
          { source: 'emails', status: 'connector_used' },
          { source: 'teams_chats', status: 'connector_used' },
          { source: 'documents_notes', status: 'connector_used' },
        ]}
        t={t}
      />,
    )

    // foundry_tool runtime: per-source previews are never available, so the panel is intentionally hidden
    // to avoid 4 empty cards showing only "プレビューはまだありません".
    expect(container.firstChild).toBeNull()
    expect(screen.queryByText('コネクタ実行')).not.toBeInTheDocument()
    expect(screen.queryByText('ソース別ステータス')).not.toBeInTheDocument()
  })

  it('keeps the panel visible when connector_used items also carry a preview or count', () => {
    render(
      <WorkIqSourceStatus
        enabled
        selectedSources={['meeting_notes', 'emails']}
        status="enabled"
        sourceMetadata={[
          { source: 'meeting_notes', status: 'connector_used', count: 2 },
          { source: 'emails', status: 'connector_used', preview: '安全な要約' },
        ]}
        t={t}
      />,
    )

    expect(screen.getAllByText('コネクタ実行')).toHaveLength(2)
    expect(screen.getByText('2 件')).toBeInTheDocument()
    expect(screen.getByText('安全な要約')).toBeInTheDocument()
  })

  it('keeps the panel visible when briefSummary is present even if all items are connector_used', () => {
    render(
      <WorkIqSourceStatus
        enabled
        selectedSources={['meeting_notes', 'emails', 'teams_chats', 'documents_notes']}
        status="enabled"
        sourceMetadata={[
          { source: 'meeting_notes', status: 'connector_used' },
          { source: 'emails', status: 'connector_used' },
          { source: 'teams_chats', status: 'connector_used' },
          { source: 'documents_notes', status: 'connector_used' },
        ]}
        briefSummary="安全な集約サマリー"
        t={t}
      />,
    )

    expect(screen.getByText('安全な集約サマリー')).toBeInTheDocument()
    expect(screen.getAllByText('コネクタ実行')).toHaveLength(4)
  })
})
