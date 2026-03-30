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
        <span>📄</span>
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
        <span className="text-xs text-green-600">✅ {fileName}</span>
      )}
      {result === 'error' && (
        <span className="text-xs text-red-500">❌ {t('pdf.error')}</span>
      )}
    </div>
  )
}
