/**
 * 多言語フック。日/英/中の切替をサポートする。
 */

import { useCallback, useEffect, useState } from 'react'
import { translations, type Locale } from '../lib/i18n'

export function useI18n() {
  const [locale, setLocaleState] = useState<Locale>(() => {
    const saved = localStorage.getItem('locale') as Locale | null
    if (saved) return saved
    const browserLocale = navigator.language.toLowerCase()
    if (browserLocale.startsWith('en')) return 'en'
    if (browserLocale.startsWith('zh')) return 'zh'
    return 'ja'
  })

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale)
    localStorage.setItem('locale', newLocale)
  }, [])

  const t = useCallback((key: string): string => {
    return translations[locale][key] || key
  }, [locale])

  useEffect(() => {
    document.documentElement.lang = locale
    document.title = translations[locale]['app.title'] || 'Travel Marketing AI'
  }, [locale])

  return { locale, setLocale, t }
}
