/**
 * i18n 翻訳データの整合性テスト
 */
import { describe, it, expect } from 'vitest'
import { translations, type Locale } from '../i18n'

const locales: Locale[] = ['ja', 'en', 'zh']

describe('i18n translations', () => {
  it('all keys in "ja" exist in "en"', () => {
    const jaKeys = Object.keys(translations.ja)
    const enKeys = Object.keys(translations.en)
    const missing = jaKeys.filter(k => !enKeys.includes(k))
    expect(missing).toEqual([])
  })

  it('all keys in "ja" exist in "zh"', () => {
    const jaKeys = Object.keys(translations.ja)
    const zhKeys = Object.keys(translations.zh)
    const missing = jaKeys.filter(k => !zhKeys.includes(k))
    expect(missing).toEqual([])
  })

  it('all keys in "en" exist in "ja"', () => {
    const enKeys = Object.keys(translations.en)
    const jaKeys = Object.keys(translations.ja)
    const missing = enKeys.filter(k => !jaKeys.includes(k))
    expect(missing).toEqual([])
  })

  it('no empty string values in any language', () => {
    for (const locale of locales) {
      const entries = Object.entries(translations[locale])
      const empties = entries.filter(([, v]) => v.trim() === '')
      expect(empties, `Empty values found in locale "${locale}"`).toEqual([])
    }
  })

  it('key count matches across all languages', () => {
    const jaCount = Object.keys(translations.ja).length
    const enCount = Object.keys(translations.en).length
    const zhCount = Object.keys(translations.zh).length
    expect(enCount).toBe(jaCount)
    expect(zhCount).toBe(jaCount)
  })
})
