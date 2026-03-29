import type { ImageContent } from '../hooks/useSSE'

interface ImageGalleryProps {
  images: ImageContent[]
  t: (key: string) => string
}

export function ImageGallery({ images, t }: ImageGalleryProps) {
  if (images.length === 0) return null

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-[var(--text-primary)]">
        {t('section.images')}
      </h3>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {images.map((img, i) => (
          <div key={i} className="overflow-hidden rounded-[24px] border border-[var(--panel-border)] bg-[var(--panel-strong)] p-3">
            <img
              src={img.url}
              alt={img.alt}
              className="h-auto w-full rounded-[18px] object-cover"
            />
            <p className="mt-2 text-xs text-[var(--text-muted)]">{img.alt}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
