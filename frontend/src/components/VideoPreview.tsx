interface VideoPreviewProps {
  videoUrl?: string
  t: (key: string) => string
}

export function VideoPreview({ videoUrl, t }: VideoPreviewProps) {
  if (!videoUrl) {
    return (
      <div className="flex items-center justify-center rounded-[24px] border border-dashed border-[var(--panel-border)] bg-[var(--panel-strong)] p-12">
        <div className="text-center">
          <p className="text-3xl">🎬</p>
          <p className="mt-3 text-sm font-medium text-[var(--text-primary)]">{t('tab.video')}</p>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">{t('tab.video.description')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-[24px] border border-[var(--panel-border)] bg-[var(--panel-strong)]">
      <video
        src={videoUrl}
        controls
        className="w-full"
        preload="metadata"
      >
        <track kind="captions" />
        {t('video.unsupported')}
      </video>
    </div>
  )
}
