import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ManagerApprovalPage } from './ManagerApprovalPage'

const t = (key: string) => ({
  'approval.manager.portal.title': '上司承認ポータル',
  'approval.manager.portal.subtitle': '企画書を確認し、承認または差し戻しを選択してください。',
  'approval.manager.portal.loading': '承認対象を読み込み中です…',
  'approval.manager.portal.invalid': 'この承認リンクは無効か期限切れです。',
  'approval.manager.portal.retry': '再読み込み',
  'approval.manager.portal.comment': 'コメント',
  'approval.manager.portal.comment.placeholder': '差し戻し理由がある場合は入力してください。',
  'approval.manager.portal.comment.required': '差し戻し時はコメントを入力してください。',
  'approval.manager.portal.submit_approve': 'この内容で承認',
  'approval.manager.portal.submit_reject': '差し戻す',
  'approval.manager.portal.approved': '承認を受け付けました。',
  'approval.manager.portal.rejected': '差し戻しを受け付けました。',
  'approval.manager.portal.fetch_error': '承認対象の取得に失敗しました。',
  'approval.manager.portal.submit_error': '承認結果の送信に失敗しました。',
  'approval.manager.portal.compare': '過去版と比較',
  'approval.manager.portal.current_version': '今回の修正版',
  'approval.manager.portal.previous_version': '以前の承認済み版',
  'approval.manager.portal.previous_version.empty': '比較対象になる以前の版はまだありません。',
  'approval.diff.title': '変更差分',
  'approval.diff.summary': '追加 {added} 行 / 削除 {removed} 行 / 変更なし {unchanged} 行',
  'approval.diff.added': '追加',
  'approval.diff.removed': '削除',
  'approval.diff.previous': '比較元',
  'approval.diff.current': '確認対象',
  'approval.diff.no_changes': '変更差分はありません。',
  'settings.manager.email': '上司メール',
}[key] ?? key)

describe('ManagerApprovalPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders manager approval as escaped text diff instead of markdown/html elements', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({
        conversation_id: 'conversation-1',
        current_version: 2,
        plan_title: 'Plan',
        plan_markdown: '# Plan\n<strong>New copy</strong>',
        previous_versions: [
          {
            version: 1,
            plan_title: 'Plan',
            plan_markdown: '# Plan\n<em>Old copy</em>',
          },
        ],
      }),
    } as Response)))

    const { container } = render(
      <ManagerApprovalPage conversationId="conversation-1" approvalToken="token" t={t} />,
    )

    expect(await screen.findByText('変更差分')).toBeInTheDocument()
    expect(screen.getByText('<em>Old copy</em>')).toBeInTheDocument()
    expect(screen.getByText('<strong>New copy</strong>')).toBeInTheDocument()
    expect(screen.getByText('以前の承認済み版: v1 · Plan')).toBeInTheDocument()
    expect(screen.getByText('今回の修正版: v2 · Plan')).toBeInTheDocument()
    expect(screen.getByLabelText('コメント')).toHaveFocus()
    expect(container.querySelector('em')).toBeNull()
    expect(container.querySelector('strong')).toBeNull()
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/chat/conversation-1/manager-approval-request',
        expect.objectContaining({
          headers: { 'X-Manager-Approval-Token': 'token' },
        }),
      )
    })
  })
  it('shows current plan without an artificial diff when there is no previous version', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({
        conversation_id: 'conversation-1',
        current_version: 1,
        plan_title: 'First Plan',
        plan_markdown: '# First Plan\nInitial copy',
        previous_versions: [],
      }),
    } as Response)))

    render(
      <ManagerApprovalPage conversationId="conversation-1" approvalToken="token" t={t} />,
    )

    expect(await screen.findByText('今回の修正版: v1 · First Plan')).toBeInTheDocument()
    expect(screen.queryByText('変更差分')).not.toBeInTheDocument()
    expect(screen.getByText(/# First Plan/)).toBeInTheDocument()
    expect(screen.getByText(/Initial copy/)).toBeInTheDocument()
    expect(screen.getByLabelText('コメント')).toHaveFocus()
  })
})
