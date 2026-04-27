import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ApprovalDiffView } from './ApprovalDiffView'

const t = (key: string) => ({
  'approval.diff.title': '変更差分',
  'approval.diff.summary': '追加 {added} 行 / 削除 {removed} 行 / 変更なし {unchanged} 行',
  'approval.diff.added': '追加',
  'approval.diff.removed': '削除',
  'approval.diff.previous': '比較元',
  'approval.diff.current': '確認対象',
  'approval.diff.no_changes': '変更差分はありません。',
}[key] ?? key)

describe('ApprovalDiffView', () => {
  it('renders line diffs for markdown text', () => {
    const { container } = render(
      <ApprovalDiffView
        previousText={'# Plan\nOld tagline\nKeep'}
        currentText={'# Plan\nNew tagline\nKeep'}
        t={t}
      />,
    )

    expect(screen.getByText('変更差分')).toBeInTheDocument()
    expect(screen.getByText('Old tagline')).toBeInTheDocument()
    expect(screen.getByText('New tagline')).toBeInTheDocument()
    expect(container.querySelectorAll('[data-diff-kind="removed"]')).toHaveLength(1)
    expect(container.querySelectorAll('[data-diff-kind="added"]')).toHaveLength(1)
  })

  it('escapes HTML-like diff content through React text rendering', () => {
    const { container } = render(
      <ApprovalDiffView
        previousText={'<script>alert("old")</script>'}
        currentText={'<strong>new</strong>'}
        t={t}
      />,
    )

    expect(screen.getByText('<script>alert("old")</script>')).toBeInTheDocument()
    expect(screen.getByText('<strong>new</strong>')).toBeInTheDocument()
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('strong')).toBeNull()
  })
})
