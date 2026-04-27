import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PdfUpload } from './PdfUpload'

const t = (key: string) => {
  const labels: Record<string, string> = {
    'pdf.upload': 'Attach PDF',
    'pdf.uploading': 'Uploading',
    'pdf.error': 'Upload failed',
    'pdf.review_required': 'Review summary',
    'pdf.approve': 'Use this PDF',
    'pdf.delete': 'Delete',
    'pdf.reviewed': 'PDF added',
  }
  return labels[key] ?? key
}

function mockFetchOnce(response: unknown, init: ResponseInit = { status: 200 }) {
  return vi.fn().mockResolvedValue({
    ok: (init.status ?? 200) >= 200 && (init.status ?? 200) < 300,
    status: init.status ?? 200,
    json: async () => response,
  })
}

describe('PdfUpload', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('uploads PDF into source review flow and approves it', async () => {
    const onConversationId = vi.fn()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          source: {
            id: 'source-1',
            conversation_id: 'conv-pdf',
            title: 'brochure.pdf',
            summary: '京都の桜ツアー要約',
            status: 'pending_review',
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          source: {
            id: 'source-1',
            conversation_id: 'conv-pdf',
            title: 'brochure.pdf',
            summary: '京都の桜ツアー要約',
            status: 'reviewed',
          },
        }),
      })
    vi.stubGlobal('fetch', fetchMock)

    render(<PdfUpload disabled={false} t={t} onConversationId={onConversationId} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File([new Uint8Array([37, 80, 68, 70, 45])], 'brochure.pdf', {
      type: 'application/pdf',
    })
    fireEvent.change(input, { target: { files: [file] } })

    expect(await screen.findByText('Review summary')).toBeInTheDocument()
    expect(screen.getByText('京都の桜ツアー要約')).toBeInTheDocument()
    expect(onConversationId).toHaveBeenCalledWith('conv-pdf')

    fireEvent.click(screen.getByRole('button', { name: 'Use this PDF' }))

    await waitFor(() => {
      expect(screen.getByText('PDF added')).toBeInTheDocument()
    })
    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/sources/pdf', expect.objectContaining({ method: 'POST' }))
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/sources/source-1/review',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('shows an error for non-PDF files without calling API', async () => {
    vi.stubGlobal('fetch', mockFetchOnce({}))
    render(<PdfUpload disabled={false} t={t} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['hello'], 'memo.txt', { type: 'text/plain' })
    fireEvent.change(input, { target: { files: [file] } })

    expect(await screen.findByText('Upload failed')).toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })
})
