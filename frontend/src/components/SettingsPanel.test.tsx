import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DEFAULT_SETTINGS, SettingsPanel } from './SettingsPanel'

const translations: Record<string, string> = {
  'settings.title': 'モデル設定',
  'settings.image.title': '画像生成設定',
  'settings.manager.title': '上司承認設定',
  'settings.model': 'モデル',
  'settings.model.desc': '使用する推論モデル',
  'settings.temperature': 'Temperature',
  'settings.temperature.desc': '値が高いほど創造的な出力',
  'settings.maxTokens': '最大トークン数',
  'settings.topP': 'Top P',
  'settings.iqResults': 'IQ 検索結果数',
  'settings.iqThreshold': 'IQ スコア閾値',
  'settings.image.model': '画像モデル',
  'settings.image.model.desc': '画像生成に使用するモデル',
  'settings.image.quality': '画質',
  'settings.image.quality.desc': '高画質ほど生成に時間がかかります',
  'settings.image.width': '幅 (px)',
  'settings.image.width.desc': 'MAI-Image-2: 最小 768px',
  'settings.image.height': '高さ (px)',
  'settings.image.height.desc': 'MAI-Image-2: 最小 768px',
  'settings.image.mai.constraint': 'constraint',
  'settings.manager.enabled': '上司承認を有効化',
  'settings.manager.enabled.desc': 'desc',
  'settings.manager.email': '上司メールアドレス',
  'settings.manager.email.desc': 'メール説明',
  'settings.manager.email.placeholder': 'manager@example.com',
  'settings.manager.email.invalid': 'invalid',
  'settings.reset': 'デフォルトに戻す',
}

function t(key: string): string {
  return translations[key] ?? key
}

describe('SettingsPanel', () => {
  it('renders separated buttons for model, image, and manager settings', () => {
    render(<SettingsPanel settings={DEFAULT_SETTINGS} onChange={() => {}} t={t} />)

    expect(screen.getByRole('button', { name: /モデル設定/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: /画像生成設定/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: /上司承認設定/ })).toBeTruthy()
  })

  it('shows only the selected manager settings section', () => {
    render(<SettingsPanel settings={DEFAULT_SETTINGS} onChange={() => {}} t={t} />)

    fireEvent.click(screen.getByRole('button', { name: /上司承認設定/ }))

    expect(screen.getByText('上司承認を有効化')).toBeTruthy()
    expect(screen.queryByLabelText('モデル')).toBeNull()
    expect(screen.queryByLabelText('画像モデル')).toBeNull()
  })
})
