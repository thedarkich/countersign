import { useEffect, useState, type ReactNode } from 'react'
import { shortAddr } from '../lib/format'
import { useLang } from '../i18n'
import { api, setAdminToken, getAdminToken } from '../api/client'
import type { EvalResults } from '../api/types'

export function Address({ value, lead = 6, tail = 4, className = '' }: { value?: string | null; lead?: number; tail?: number; className?: string }) {
  const { t } = useLang()
  const [copied, setCopied] = useState(false)
  if (!value) return <span className="text-ink2">—</span>
  return (
    <button
      type="button"
      title={value}
      onClick={() => {
        navigator.clipboard?.writeText(value).then(() => {
          setCopied(true)
          setTimeout(() => setCopied(false), 1200)
        })
      }}
      className={`font-mono text-[0.85em] underline decoration-rule decoration-dotted underline-offset-4 hover:decoration-ink ${className}`}
    >
      {copied ? t.copied : shortAddr(value, lead, tail)}
    </button>
  )
}

export function TxLink({ href, hash, label }: { href?: string | null; hash?: string | null; label?: string }) {
  if (!href || !hash) return <span className="text-ink2">—</span>
  return (
    <a href={href} target="_blank" rel="noreferrer" className={`${!label || label.startsWith('0x') ? 'font-mono text-[0.85em]' : ''} underline decoration-rule underline-offset-4 hover:decoration-ink`} title={hash}>
      {label ?? shortAddr(hash, 8, 6)}
    </a>
  )
}

/** Live countdown to an ISO time; calls onDone once when it passes. */
export function Countdown({ to, onDone }: { to: string; onDone?: () => void }) {
  const target = new Date(to).getTime()
  const [left, setLeft] = useState(() => Math.max(0, target - Date.now()))
  useEffect(() => {
    const t = setInterval(() => {
      const l = Math.max(0, target - Date.now())
      setLeft(l)
      if (l === 0) {
        clearInterval(t)
        onDone?.()
      }
    }, 250)
    return () => clearInterval(t)
  }, [target, onDone])
  const s = Math.ceil(left / 1000)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const txt = h > 0 ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}` : `${m}:${String(sec).padStart(2, '0')}`
  return <span className="num cond font-bold">{txt}</span>
}

export function AdminGate({ children }: { children: ReactNode }) {
  const { t, tr } = useLang()
  const [token, setToken] = useState(getAdminToken() ?? '')
  const [ok, setOk] = useState(!!getAdminToken())
  if (ok) return <>{children}</>
  return (
    <main tabIndex={-1} className="mx-auto mt-16 max-w-md rounded-box border border-rule bg-field p-6">
      <h1 className="cond text-3xl font-bold">{t.admin_title}</h1>
      <p className="mt-2 text-ink2">{t.admin_body}</p>
      {api.mode === 'mock' && <p className="mt-3 text-sm text-ink2">{tr('Mock preview: enter any text to explore. No wallet is needed.', '模拟预览：输入任意文字即可体验，无需钱包。')}</p>}
      <form
        className="mt-5 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (!token.trim()) return
          setAdminToken(token.trim())
          setOk(true)
        }}
      >
        <input className="field" type="password" autoComplete="off" placeholder={t.admin_ph} value={token} onChange={(e) => setToken(e.target.value)} aria-label={t.admin_ph} />
        <button className="btn btn-ink" type="submit">
          {t.admin_go}
        </button>
      </form>
    </main>
  )
}

/** Guard v1 vs v2 on held-out attacks. Renders nothing until results exist. */
export function EvalCard({ data, large = false }: { data?: EvalResults; large?: boolean }) {
  const { t, tr } = useLang()
  if (!data?.v1 || !data?.v2) return null
  const row = (label: string, a: number, b: number, goodUp: boolean) => {
    const better = goodUp ? b > a : b < a
    return (
      <div className="grid grid-cols-[1fr_auto_auto_auto] items-baseline gap-x-3">
        <span className={large ? 'text-lg' : ''}>{label}</span>
        <span className={`num cond font-bold text-ink2 ${large ? 'text-3xl' : 'text-xl'}`}>{Math.round(a * 100)}%</span>
        <span className="text-ink2" aria-hidden>
          ›
        </span>
        <span className={`num cond-x font-bold ${large ? 'text-5xl' : 'text-3xl'}`} style={{ color: better ? 'var(--jade)' : 'var(--ink)' }}>
          {Math.round(b * 100)}%
        </span>
      </div>
    )
  }
  return (
    <section className="ruled bg-field p-4" aria-label={t.eval_title}>
      <h2 className={`cond font-bold ${large ? 'text-2xl' : 'text-lg'}`}>{t.eval_title}</h2>
      <p className="mb-3 text-sm text-ink2">
        {t.eval_sub}
        {data.n_heldout_attacks ? tr(` (${data.n_heldout_attacks} attacks, ${data.n_heldout_clean} clean invoices)`, `（${data.n_heldout_attacks} 次攻击，${data.n_heldout_clean} 张正常发票）`) : ''}
      </p>
      <div className={`mb-1 grid grid-cols-[1fr_auto_auto_auto] gap-x-3 text-xs text-ink2 ${large ? '' : 'max-w-[26rem]'}`}>
        <span />
        <span>v1</span>
        <span />
        <span>v2</span>
      </div>
      <div className={`space-y-1.5 ${large ? '' : 'max-w-[26rem]'}`}>
        {row(t.eval_catch, data.v1.catch, data.v2.catch, true)}
        {row(t.eval_false, data.v1.false_alarm, data.v2.false_alarm, false)}
      </div>
    </section>
  )
}
