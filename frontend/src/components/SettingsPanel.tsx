/**
 * モデル設定パネル。Temperature / Max Tokens / Top P / Foundry IQ パラメータを調整する。
 */

import { ChevronDown, ImagePlus, ShieldCheck, SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'

export interface ModelSettings {
  model: string
  temperature: number
  maxTokens: number
  topP: number
  iqSearchResults: number
  iqScoreThreshold: number
  imageModel: string
  imageQuality: string
  imageWidth: number
  imageHeight: number
  managerApprovalEnabled: boolean
  managerEmail: string
}

// eslint-disable-next-line react-refresh/only-export-components
export const DEFAULT_SETTINGS: ModelSettings = {
  model: 'gpt-5-4-mini',
  temperature: 0.7,
  maxTokens: 16384,
  topP: 1.0,
  iqSearchResults: 5,
  iqScoreThreshold: 0.0,
  imageModel: 'gpt-image-1.5',
  imageQuality: 'medium',
  imageWidth: 1024,
  imageHeight: 1024,
  managerApprovalEnabled: false,
  managerEmail: '',
}

const MANAGER_EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const AVAILABLE_MODELS = [
  { value: 'gpt-5-4-mini', label: 'GPT-5.4 mini (default)' },
  { value: 'gpt-5.4', label: 'GPT-5.4' },
  { value: 'gpt-4-1-mini', label: 'GPT-4.1 mini' },
  { value: 'gpt-4.1', label: 'GPT-4.1' },
]

const AVAILABLE_IMAGE_MODELS = [
  { value: 'gpt-image-1.5', label: 'GPT Image 1.5 (default)' },
  { value: 'MAI-Image-2', label: 'MAI-Image-2' },
]

const IMAGE_QUALITY_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
]

interface SettingsPanelProps {
  settings: ModelSettings
  onChange: (settings: ModelSettings) => void
  t: (key: string) => string
}

type SettingsSection = 'model' | 'image' | 'manager'

interface SliderFieldProps {
  inputId: string
  label: string
  tooltip: string
  value: number
  min: number
  max: number
  step: number
  onChange: (value: number) => void
}

function SliderField({ inputId, label, tooltip, value, min, max, step, onChange }: SliderFieldProps) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label htmlFor={inputId} className="text-xs font-medium text-[var(--text-secondary)]" title={tooltip}>
          {label}
          <span className="ml-1 cursor-help text-[var(--text-muted)]" title={tooltip}>ⓘ</span>
        </label>
        <span className="rounded bg-[var(--panel-strong)] px-2 py-0.5 text-xs font-mono text-[var(--text-primary)]">
          {value}
        </span>
      </div>
      <input
        id={inputId}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-[var(--accent-strong)] h-1.5 cursor-pointer appearance-none rounded-full bg-[var(--panel-border)]
          [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:appearance-none
          [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[var(--accent-strong)]
          [&::-webkit-slider-thumb]:shadow-sm [&::-webkit-slider-thumb]:transition-transform
          [&::-webkit-slider-thumb]:hover:scale-110"
      />
    </div>
  )
}

export function SettingsPanel({ settings, onChange, t }: SettingsPanelProps) {
  const [activeSection, setActiveSection] = useState<SettingsSection | null>(null)
  const trimmedManagerEmail = settings.managerEmail.trim()
  const isManagerEmailInvalid = settings.managerApprovalEnabled
    && trimmedManagerEmail.length > 0
    && !MANAGER_EMAIL_PATTERN.test(trimmedManagerEmail)

  const sectionOptions: Array<{ key: SettingsSection; label: string; Icon: typeof SlidersHorizontal }> = [
    { key: 'model', label: t('settings.title'), Icon: SlidersHorizontal },
    { key: 'image', label: t('settings.image.title'), Icon: ImagePlus },
    { key: 'manager', label: t('settings.manager.title'), Icon: ShieldCheck },
  ]

  const update = (key: keyof ModelSettings, value: number | string | boolean) => {
    onChange({ ...settings, [key]: value })
  }

  const resetSectionDefaults = (section: SettingsSection) => {
    if (section === 'model') {
      onChange({
        ...settings,
        model: DEFAULT_SETTINGS.model,
        temperature: DEFAULT_SETTINGS.temperature,
        maxTokens: DEFAULT_SETTINGS.maxTokens,
        topP: DEFAULT_SETTINGS.topP,
        iqSearchResults: DEFAULT_SETTINGS.iqSearchResults,
        iqScoreThreshold: DEFAULT_SETTINGS.iqScoreThreshold,
      })
      return
    }

    if (section === 'image') {
      onChange({
        ...settings,
        imageModel: DEFAULT_SETTINGS.imageModel,
        imageQuality: DEFAULT_SETTINGS.imageQuality,
        imageWidth: DEFAULT_SETTINGS.imageWidth,
        imageHeight: DEFAULT_SETTINGS.imageHeight,
      })
      return
    }

    onChange({
      ...settings,
      managerApprovalEnabled: DEFAULT_SETTINGS.managerApprovalEnabled,
      managerEmail: DEFAULT_SETTINGS.managerEmail,
    })
  }

  const toggleSection = (section: SettingsSection) => {
    setActiveSection(current => current === section ? null : section)
  }

  return (
    <div className="mb-3">
      <div className="flex flex-wrap gap-2">
        {sectionOptions.map(({ key, label, Icon }) => {
          const isOpen = activeSection === key
          return (
            <button
              key={key}
              type="button"
              onClick={() => toggleSection(key)}
              className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${isOpen
                ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)]'
                : 'border-[var(--panel-border)] text-[var(--text-secondary)] hover:bg-[var(--panel-strong)] hover:text-[var(--text-primary)]'}`}
            >
              <Icon className="h-3.5 w-3.5" />
              <span>{label}</span>
              <ChevronDown className={`h-3.5 w-3.5 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>
          )
        })}
      </div>

      {activeSection && (
        <div className="mt-2 rounded-2xl border border-[var(--panel-border)] bg-[var(--panel-bg)] p-4 shadow-sm">
          <div className="mb-4 flex items-center justify-between gap-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
              {sectionOptions.find(section => section.key === activeSection)?.label}
            </p>
            <button
              type="button"
              onClick={() => resetSectionDefaults(activeSection)}
              className="rounded-full border border-[var(--panel-border)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--panel-strong)] hover:text-[var(--text-primary)]"
            >
              {t('settings.reset')}
            </button>
          </div>

          {activeSection === 'model' && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label htmlFor="settings-model" className="text-xs font-medium text-[var(--text-secondary)]" title={t('settings.model.desc')}>
                    {t('settings.model')}
                    <span className="ml-1 cursor-help text-[var(--text-muted)]" title={t('settings.model.desc')}>ⓘ</span>
                  </label>
                </div>
                <select
                  id="settings-model"
                  value={settings.model}
                  onChange={(e) => update('model', e.target.value)}
                  aria-label={t('settings.model')}
                  className="w-full rounded-md border border-[var(--panel-border)] bg-[var(--panel-strong)] px-2 py-1.5 text-xs font-mono text-[var(--text-primary)] accent-[var(--accent-strong)] cursor-pointer focus:outline-none focus:ring-1 focus:ring-[var(--accent-strong)]"
                >
                  {AVAILABLE_MODELS.map((m) => (
                    <option key={m.value} value={m.value}>{m.label}</option>
                  ))}
                </select>
              </div>
              <SliderField
                inputId="settings-temperature"
                label={t('settings.temperature')}
                tooltip={t('settings.temperature.desc')}
                value={settings.temperature}
                min={0}
                max={2}
                step={0.1}
                onChange={(v) => update('temperature', v)}
              />
              <SliderField
                inputId="settings-max-tokens"
                label={t('settings.maxTokens')}
                tooltip={t('settings.maxTokens')}
                value={settings.maxTokens}
                min={256}
                max={16384}
                step={256}
                onChange={(v) => update('maxTokens', v)}
              />
              <SliderField
                inputId="settings-top-p"
                label={t('settings.topP')}
                tooltip="Top P"
                value={settings.topP}
                min={0}
                max={1}
                step={0.05}
                onChange={(v) => update('topP', v)}
              />
              <SliderField
                inputId="settings-iq-results"
                label={t('settings.iqResults')}
                tooltip={t('settings.iqResults')}
                value={settings.iqSearchResults}
                min={1}
                max={20}
                step={1}
                onChange={(v) => update('iqSearchResults', v)}
              />
              <SliderField
                inputId="settings-iq-threshold"
                label={t('settings.iqThreshold')}
                tooltip={t('settings.iqThreshold')}
                value={settings.iqScoreThreshold}
                min={0}
                max={1}
                step={0.05}
                onChange={(v) => update('iqScoreThreshold', v)}
              />
            </div>
          )}

          {activeSection === 'image' && (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label htmlFor="settings-image-model" className="text-xs font-medium text-[var(--text-secondary)]" title={t('settings.image.model.desc')}>
                    {t('settings.image.model')}
                    <span className="ml-1 cursor-help text-[var(--text-muted)]" title={t('settings.image.model.desc')}>ⓘ</span>
                  </label>
                </div>
                <select
                  id="settings-image-model"
                  value={settings.imageModel}
                  onChange={(e) => update('imageModel', e.target.value)}
                  aria-label={t('settings.image.model')}
                  className="w-full rounded-md border border-[var(--panel-border)] bg-[var(--panel-strong)] px-2 py-1.5 text-xs font-mono text-[var(--text-primary)] accent-[var(--accent-strong)] cursor-pointer focus:outline-none focus:ring-1 focus:ring-[var(--accent-strong)]"
                >
                  {AVAILABLE_IMAGE_MODELS.map((m) => (
                    <option key={m.value} value={m.value}>{m.label}</option>
                  ))}
                </select>
              </div>

              {settings.imageModel === 'gpt-image-1.5' && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label htmlFor="settings-image-quality" className="text-xs font-medium text-[var(--text-secondary)]" title={t('settings.image.quality.desc')}>
                      {t('settings.image.quality')}
                      <span className="ml-1 cursor-help text-[var(--text-muted)]" title={t('settings.image.quality.desc')}>ⓘ</span>
                    </label>
                  </div>
                  <select
                    id="settings-image-quality"
                    value={settings.imageQuality}
                    onChange={(e) => update('imageQuality', e.target.value)}
                    aria-label={t('settings.image.quality')}
                    className="w-full rounded-md border border-[var(--panel-border)] bg-[var(--panel-strong)] px-2 py-1.5 text-xs font-mono text-[var(--text-primary)] accent-[var(--accent-strong)] cursor-pointer focus:outline-none focus:ring-1 focus:ring-[var(--accent-strong)]"
                  >
                    {IMAGE_QUALITY_OPTIONS.map((q) => (
                      <option key={q.value} value={q.value}>{q.label}</option>
                    ))}
                  </select>
                </div>
              )}

              {settings.imageModel === 'MAI-Image-2' && (
                <>
                  <SliderField
                    inputId="settings-image-width"
                    label={t('settings.image.width')}
                    tooltip={t('settings.image.width.desc')}
                    value={settings.imageWidth}
                    min={768}
                    max={1024}
                    step={16}
                    onChange={(v) => update('imageWidth', v)}
                  />
                  <SliderField
                    inputId="settings-image-height"
                    label={t('settings.image.height')}
                    tooltip={t('settings.image.height.desc')}
                    value={settings.imageHeight}
                    min={768}
                    max={1024}
                    step={16}
                    onChange={(v) => update('imageHeight', v)}
                  />
                </>
              )}
              </div>
              {settings.imageModel === 'MAI-Image-2' && (
                <p className="mt-2 text-[10px] text-[var(--text-muted)]">
                  {t('settings.image.mai.constraint')}
                </p>
              )}
            </>
          )}

          {activeSection === 'manager' && (
            <div className="space-y-3">
              <label
                htmlFor="settings-manager-approval"
                className="flex items-center justify-between rounded-xl border border-[var(--panel-border)] bg-[var(--panel-strong)] px-3 py-2.5"
              >
                <div className="pr-4">
                  <p className="text-xs font-medium text-[var(--text-primary)]">{t('settings.manager.enabled')}</p>
                  <p className="mt-1 text-[11px] text-[var(--text-muted)]">{t('settings.manager.enabled.desc')}</p>
                </div>
                <input
                  id="settings-manager-approval"
                  type="checkbox"
                  checked={settings.managerApprovalEnabled}
                  onChange={(e) => update('managerApprovalEnabled', e.target.checked)}
                  className="h-4 w-4 rounded border-[var(--panel-border)] text-[var(--accent-strong)] focus:ring-[var(--accent-strong)]"
                />
              </label>

              {settings.managerApprovalEnabled && (
                <div className="space-y-1.5">
                  <label
                    htmlFor="settings-manager-email"
                    className="text-xs font-medium text-[var(--text-secondary)]"
                    title={t('settings.manager.email.desc')}
                  >
                    {t('settings.manager.email')}
                    <span className="ml-1 cursor-help text-[var(--text-muted)]" title={t('settings.manager.email.desc')}>ⓘ</span>
                  </label>
                  <input
                    id="settings-manager-email"
                    type="email"
                    value={settings.managerEmail}
                    onChange={(e) => update('managerEmail', e.target.value)}
                    placeholder={t('settings.manager.email.placeholder')}
                    className="w-full rounded-md border border-[var(--panel-border)] bg-[var(--panel-strong)] px-3 py-2 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-strong)]"
                  />
                  {isManagerEmailInvalid && (
                    <p className="text-[11px] text-rose-500">{t('settings.manager.email.invalid')}</p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
