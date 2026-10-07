import { Moon, Sun } from 'lucide-react'
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
      className="inline-flex h-[1.9rem] w-[1.9rem] shrink-0 items-center justify-center rounded-md text-ink-2 hover:bg-paper2 hover:text-ink"
    >
      {dark ? <Sun size={17} /> : <Moon size={17} />}
    </button>
  )
}
