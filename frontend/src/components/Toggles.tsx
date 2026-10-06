import { useLang } from '../i18n'
import { useTheme } from '../lib/theme'

/** 中文 / EN, both always visible so nobody has to guess that the page comes in two languages. */
export function LangSwitch({ size = 'md' }: { size?: 'md' | 'lg' }) {
  const { lang, setLang } = useLang()
  const pad = size === 'lg' ? 'px-3 py-1.5' : 'px-2 py-1'
  return (
    <div role="group" aria-label="语言 Language" className="flex shrink-0 overflow-hidden rounded-box border border-ink text-sm font-semibold leading-none">
      {(
        [
          ['zh', '中文', '中'],
          ['en', 'EN', 'EN'],
        ] as const
      ).map(([code, full, short]) => (
        <button
          key={code}
          type="button"
          lang={code === 'zh' ? 'zh-CN' : 'en'}
          aria-pressed={lang === code}
          onClick={() => setLang(code)}
          className={`${pad} ${lang === code ? 'bg-ink text-field' : 'text-ink hover:bg-paper2'}`}
        >
          <span className="sm:hidden">{short}</span>
          <span className="hidden sm:inline">{full}</span>
        </button>
      ))}
    </div>
  )
}

export function ThemeSwitch() {
  const { tr } = useLang()
  const [theme, setTheme] = useTheme()
  const dark = theme === 'dark'
  const label = dark ? tr('Light theme', '浅色模式') : tr('Dark theme', '深色模式')
  return (
    <button
      type="button"
      onClick={() => setTheme(dark ? 'light' : 'dark')}
      aria-label={label}
      title={label}
      className="inline-flex h-[1.9rem] w-[1.9rem] shrink-0 items-center justify-center rounded-box text-ink hover:bg-paper2"
    >
      {dark ? (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
          <circle cx="12" cy="12" r="4.2" />
          <path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6" />
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" aria-hidden>
          <path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5a8.5 8.5 0 1 0 10.7 10.7Z" />
        </svg>
      )}
    </button>
  )
}
