import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MarkdownView } from './MarkdownView'

describe('MarkdownView', () => {
  it('strips raw Foundry/Web Search citation markers before rendering', () => {
    const { container } = render(<MarkdownView content={'需要が高い。 \ue200cite\ue202turn0search0\ue201'} />)

    expect(screen.getByText('需要が高い。')).toBeInTheDocument()
    expect(container.textContent).not.toContain('cite')
    expect(container.textContent).not.toContain('turn0search0')
  })

  it('allows safe markdown links and images', () => {
    render(<MarkdownView content={'[source](https://example.com/report)\n\n![chart](data:image/png;base64,abc123)'} />)

    expect(screen.getByRole('link', { name: 'source' })).toHaveAttribute('href', 'https://example.com/report')
    expect(screen.getByRole('img', { name: 'chart' })).toHaveAttribute('src', 'data:image/png;base64,abc123')
  })

  it('blocks unsafe markdown link protocols', () => {
    render(<MarkdownView content={'[bad](javascript:alert(1))'} />)

    expect(screen.queryByRole('link', { name: 'bad' })).toBeNull()
    expect(screen.getByText('bad')).toBeInTheDocument()
  })

  it('blocks unsafe markdown image protocols', () => {
    const { container } = render(<MarkdownView content={'![bad](javascript:alert(1))'} />)

    expect(container.querySelector('img')).toBeNull()
  })
})

