import { useRef, useState } from 'react'

const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10 MB

interface PdfUploadProps {
  disabled: boolean
  t: (key: string) => string
}

export function PdfUpload({ disabled, t }: PdfUploadProps) {
  const [fileName, setFileName] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<'success' | 'error' | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setResult('error')
      return
    }
    if (file.size > MAX_FILE_SIZE) {
      setResult('error')
      return
    }

    setFileName(file.name)
    setUploading(true)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/api/upload-pdf', {
        method: 'POST',
        body: formData,
      })
      setResult(res.ok ? 'success' : 'error')
    } catch {
      setResult('error')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <div className="flex items-center gap-2">
      <label
        className={`flex cursor-pointer items-center gap-1.5 rounded-full border border-[var(--input-border)] bg-[var(--input-bg)] px-3 py-2 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:border-[var(--accent)] hover:text-[var(--accent-strong)] ${disabled || uploading ? 'pointer-events-none opacity-40' : ''}`}
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>
        <span>{t('pdf.upload')}</span>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={handleChange}
          disabled={disabled || uploading}
        />
      </label>
      {uploading && <span className="text-xs text-[var(--text-muted)]">{t('pdf.uploading')}</span>}
      {result === 'success' && fileName && (
        <span className="inline-flex items-center gap-1 text-xs text-green-600"><svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg> {fileName}</span>
      )}
      {result === 'error' && (
        <span className="inline-flex items-center gap-1 text-xs text-red-500"><svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg> {t('pdf.error')}</span>
      )}
    </div>
  )
}
