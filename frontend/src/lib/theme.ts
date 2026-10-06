import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'
const KEY = 'cs_theme'
const BAR = { light: '#f5f6f5', dark: '#0b0e0c' }

const media = () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null)

function saved(): Theme | null {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null
  }
}

function apply(t: Theme) {
  document.documentElement.setAttribute('data-theme', t)
  // phones colour the browser bar from theme-color; keep it in step with an explicit choice
  document.querySelectorAll('meta[name="theme-color"]').forEach((m) => m.setAttribute('content', BAR[t]))
}

/** The current theme: the saved choice if there is one, otherwise whatever the system uses. */
export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setThemeState] = useState<Theme>(() => saved() ?? (media()?.matches ? 'dark' : 'light'))

  useEffect(() => {
    const m = media()
    if (!m || saved()) return
    const on = (e: MediaQueryListEvent) => setThemeState(e.matches ? 'dark' : 'light')
    m.addEventListener?.('change', on)
    return () => m.removeEventListener?.('change', on)
  }, [])

  const setTheme = (t: Theme) => {
    setThemeState(t)
    apply(t)
    try {
      localStorage.setItem(KEY, t)
    } catch {
      /* storage blocked: the choice lasts for this page */
    }
  }
  return [theme, setTheme]
}
