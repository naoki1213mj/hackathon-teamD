import { describe, expect, it } from 'vitest'
import { buildTextDiff, summarizeTextDiff } from '../text-diff'

describe('text-diff', () => {
  it('marks added and removed markdown lines', () => {
    const diff = buildTextDiff('# Plan\nOld copy\nKeep', '# Plan\nNew copy\nKeep\nCTA')

    expect(diff).toEqual([
      { type: 'unchanged', text: '# Plan' },
      { type: 'removed', text: 'Old copy' },
      { type: 'added', text: 'New copy' },
      { type: 'unchanged', text: 'Keep' },
      { type: 'added', text: 'CTA' },
    ])
    expect(summarizeTextDiff(diff)).toEqual({ added: 2, removed: 1, unchanged: 2 })
  })

  it('treats a missing previous version as all added content', () => {
    const diff = buildTextDiff('', 'Line 1\nLine 2')

    expect(diff).toEqual([
      { type: 'added', text: 'Line 1' },
      { type: 'added', text: 'Line 2' },
    ])
  })
})
