import type { TextContent } from '../hooks/useSSE'

export type VideoWorkflowStatus = 'idle' | 'pending' | 'completed' | 'issue'

function normalizeVideoStatusMessage(rawContent: string): string | undefined {
  const trimmed = rawContent.trim()
  if (!trimmed) return undefined

  try {
    const parsed = JSON.parse(trimmed) as { message?: unknown; status?: unknown }
    if (typeof parsed.message === 'string' && parsed.message.trim()) {
      return parsed.message.trim()
    }
    if (typeof parsed.status === 'string' && parsed.status.trim()) {
      return parsed.status.trim()
    }
  } catch {
    // JSON 以外のプレーンテキストはそのまま扱う。
  }

  return trimmed
}

export function extractVideoUrl(textContents: TextContent[]): string | undefined {
  const videoEntry = textContents.findLast(content => content.agent === 'video-gen-agent' && content.content_type === 'video')
  const url = videoEntry?.content.trim()
  return url || undefined
}

export function extractVideoStatusMessage(textContents: TextContent[]): string | undefined {
  const statusEntry = textContents.findLast(content => content.agent === 'video-gen-agent' && content.content_type !== 'video')
  if (!statusEntry) return undefined
  return normalizeVideoStatusMessage(statusEntry.content)
}

export function classifyVideoWorkflowStatus(
  textContents: TextContent[],
  backgroundUpdatesPending: boolean,
): VideoWorkflowStatus {
  if (extractVideoUrl(textContents)) {
    return 'completed'
  }

  const statusMessage = extractVideoStatusMessage(textContents)
  if (backgroundUpdatesPending) {
    return statusMessage ? 'pending' : 'idle'
  }

  return statusMessage ? 'issue' : 'idle'
}
