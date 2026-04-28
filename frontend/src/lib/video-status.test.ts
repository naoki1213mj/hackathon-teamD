import { describe, expect, it } from 'vitest'
import type { TextContent } from '../hooks/useSSE'
import { classifyVideoWorkflowStatus, extractVideoUrl } from './video-status'

describe('video status helpers', () => {
  it('returns only safe HTTP(S) video URLs', () => {
    const safeContents: TextContent[] = [
      { agent: 'video-gen-agent', content_type: 'video', content: 'https://example.com/video.mp4' },
    ]
    const unsafeContents: TextContent[] = [
      { agent: 'video-gen-agent', content_type: 'video', content: 'javascript:alert(1)' },
    ]
    const signedContents: TextContent[] = [
      { agent: 'video-gen-agent', content_type: 'video', content: 'https://example.com/video.mp4?sig=secret' },
    ]

    expect(extractVideoUrl(safeContents)).toBe('https://example.com/video.mp4')
    expect(extractVideoUrl(unsafeContents)).toBeUndefined()
    expect(extractVideoUrl(signedContents)).toBe('https://example.com/video.mp4?sig=secret')
    expect(classifyVideoWorkflowStatus(unsafeContents, false)).toBe('idle')
  })

  it('classifies warning messages as an issue even while other background updates are pending', () => {
    const warningContents: TextContent[] = [
      {
        agent: 'video-gen-agent',
        content_type: 'text',
        content: '⚠️ 動画生成ジョブの送信がタイムアウトしました。',
      },
    ]

    expect(classifyVideoWorkflowStatus(warningContents, true)).toBe('issue')
  })
})
