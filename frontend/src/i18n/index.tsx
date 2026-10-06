import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { en, zh, type Strings } from './strings'

export type Lang = 'zh' | 'en'
type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: Strings; tr: (en: string, zh: string) => string }
const LangContext = createContext<Ctx | null>(null)

const KEY = 'cs_lang'
function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'zh' || saved === 'en') return saved
  } catch {
    /* ignore */
  }
  // first visit: follow the phone or browser language (WeChat on a mainland phone reports zh-CN)
  const nav = (navigator.languages?.[0] ?? navigator.language ?? '').toLowerCase()
  return nav.startsWith('zh') ? 'zh' : 'en'
}

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang)
  useEffect(() => {
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en'
  }, [lang])
  const value = useMemo<Ctx>(() => {
    const setLang = (l: Lang) => {
      setLangState(l)
      try {
        localStorage.setItem(KEY, l)
      } catch {
        /* ignore */
      }
    }
    return { lang, setLang, t: lang === 'zh' ? zh : en, tr: (e, z) => (lang === 'zh' ? z : e) }
  }, [lang])
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>
}

export function useLang(): Ctx {
  const c = useContext(LangContext)
  if (!c) throw new Error('useLang outside LangProvider')
  return c
}
