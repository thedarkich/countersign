import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, RateLimitedError } from '../api/client'
import type { AgentKind, Attempt } from '../api/types'
import { useLang } from '../i18n'
import { Header } from '../components/Header'
import { Seal } from '../components/Seal'
import { StepRow } from '../components/StepRow'
import { Counters } from '../components/Counters'
import { TxLink } from '../components/bits'
import { flagLabel, reasonLabel } from '../lib/reasons'
import { isAddress, timeAgo } from '../lib/format'
import { kb, prepareUpload, UploadError } from '../lib/upload'

export default function BountyPage() {
  const { t, lang } = useLang()
  const config = useQuery({ queryKey: ['config'], queryFn: api.config, staleTime: 60_000 })
  const stats = useQuery({ queryKey: ['stats'], queryFn: api.stats, refetchInterval: 3000 })
  const board = useQuery({ queryKey: ['leaderboard'], queryFn: api.leaderboard, refetchInterval: 5000 })
  const [attemptId, setAttemptId] = useState<string | null>(null)
  const symbol = config.data?.token.symbol ?? ''
  const testnet = (config.data?.bounty_network ?? config.data?.network) === 'testnet'
  const serial = String((stats.data?.outside.attempts ?? 0) + 1).padStart(6, '0')

  return (
    <div className="min-h-dvh">
      <Header />
      <main className="mx-auto grid max-w-6xl gap-x-10 gap-y-8 px-4 pb-16 pt-6 lg:grid-cols-[1.05fr_0.95fr] lg:pt-10">
        <section className="lg:pt-2">
          <h1 className="cond keep text-[2.6rem] font-extrabold leading-[1.08] sm:text-[3.4rem]">{t.hero}</h1>
          <p className="mt-4 max-w-[34rem] text-[1.02rem] text-ink2">{t.hero_sub}</p>
          {testnet && (
            <p className="mt-3 inline-block border-l-2 border-cinnabar pl-2.5 text-sm text-ink">
              {lang === 'zh' ? '这个挑战跑在 BOT Chain 测试网上，金库里是没有真实价值的测试代币。' : 'This challenge runs on BOT Chain testnet. The vault holds test tokens with no real value.'}
            </p>
          )}

          {/* two prizes as tear-off counterfoils */}
          <div className="mt-7 grid grid-cols-2 overflow-hidden ruled bg-field">
            <Prize title={t.prize_fool_title} body={t.prize_fool_body} reward={t.prize_fool_reward} />
            <div className="border-l-2 border-dashed border-rule">
              <Prize title={t.prize_rob_title} body={t.prize_rob_body} reward={t.prize_rob_reward} strong />
            </div>
          </div>

          <div className="mt-8 hidden lg:block">
            <CountersBlock stats={stats.data} symbol={symbol} />
            <Leaderboard entries={board.data} />
          </div>
        </section>

        <section aria-label={t.form_title}>
          <div className="lg:sticky lg:top-4">
            {attemptId ? (
              <Result id={attemptId} onAgain={() => setAttemptId(null)} />
            ) : (
              <SubmitForm serial={serial} onSubmitted={setAttemptId} />
            )}
          </div>
        </section>

        <section className="lg:hidden">
          <CountersBlock stats={stats.data} symbol={symbol} />
          <Leaderboard entries={board.data} />
        </section>

        <section className="max-w-[40rem] lg:col-span-2">
          <h2 className="cond text-xl font-bold">{t.rules_title}</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-ink2">
            {t.rules.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <p className="mt-4 text-sm text-ink2">{t.privacy}</p>
        </section>
      </main>
    </div>
  )
}

function Prize({ title, body, reward, strong }: { title: string; body: string; reward: string; strong?: boolean }) {
  return (
    <div className="flex h-full flex-col p-3.5 sm:p-4">
      <h3 className="cond text-[1.35rem] font-bold leading-tight" style={{ color: strong ? 'var(--cinnabar)' : 'var(--ink)' }}>
        {title}
      </h3>
      <p className="mt-1.5 flex-1 text-[0.92rem] leading-snug text-ink2">{body}</p>
      <p className="rule-t mt-3 pt-2 text-sm font-semibold">{reward}</p>
    </div>
  )
}

function CountersBlock({ stats, symbol }: { stats?: import('../api/types').Stats; symbol: string }) {
  const { t } = useLang()
  return (
    <div>
      <h2 className="cond mb-2 text-xl font-bold">{t.counters_title}</h2>
      <Counters stats={stats?.outside} symbol={symbol} />
      {stats && stats.seed.attempts > 0 && <p className="mt-2 text-sm text-ink2">{t.c_seed_note.replace('{n}', String(stats.seed.attempts))}</p>}
    </div>
  )
}

function Leaderboard({ entries }: { entries?: import('../api/types').LeaderboardEntry[] }) {
  const { t, lang } = useLang()
  const guarded = (entries ?? []).filter((e) => e.agent === 'guarded')
  return (
    <div className="mt-8">
      <h2 className="cond text-xl font-bold">{t.board_title}</h2>
      {guarded.length === 0 ? (
        <p className="mt-2 text-ink2">{t.board_empty}</p>
      ) : (
        <ol className="mt-2 divide-y divide-rule ruled bg-field">
          {guarded.slice(0, 10).map((e, i) => (
            <li key={e.attempt_id} className="grid grid-cols-[2rem_1fr_auto] items-baseline gap-2 px-3 py-2.5">
              <span className="num cond font-bold text-ink2">{i + 1}</span>
              <span>
                <span className="font-semibold">{e.nickname}</span>
                <span className="block text-sm leading-snug text-ink2">{lang === 'zh' ? e.summary_zh : e.summary_en}</span>
              </span>
              <span className="whitespace-nowrap text-xs text-ink2">{timeAgo(e.created_at, lang)}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

function SubmitForm({ serial, onSubmitted }: { serial: string; onSubmitted: (id: string) => void }) {
  const { t, lang } = useLang()
  const [nickname, setNickname] = useState(() => {
    try {
      return localStorage.getItem('cs_nick') ?? ''
    } catch {
      return ''
    }
  })
  const [address, setAddress] = useState('')
  const [agent, setAgent] = useState<AgentKind>('guarded')
  const [mode, setMode] = useState<'upload' | 'message'>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [shrinking, setShrinking] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  async function pick(f: File | null) {
    setError(null)
    setFile(null)
    if (!f) return
    setShrinking(true)
    try {
      setFile(await prepareUpload(f))
    } catch (err) {
      setError(err instanceof UploadError && err.code === 'wrong_type' ? t.upload_wrong_type : t.upload_too_big)
      if (fileRef.current) fileRef.current.value = ''
    } finally {
      setShrinking(false)
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!nickname.trim()) return setError(t.need_nickname)
    if (address.trim() && !isAddress(address)) return setError(t.bad_address)
    if (mode === 'upload' ? !file : !text.trim()) return setError(t.need_input)
    setBusy(true)
    try {
      try {
        localStorage.setItem('cs_nick', nickname.trim())
      } catch {
        /* ignore */
      }
      const r = await api.submitBounty({
        nickname: nickname.trim(),
        address: address.trim() || undefined,
        agent,
        text: mode === 'message' ? text.trim() : undefined,
        file: mode === 'upload' ? file : null,
      })
      onSubmitted(r.attempt_id)
    } catch (err) {
      if (err instanceof RateLimitedError) setError(lang === 'zh' ? err.message_zh : err.message_en)
      else setError(t.submit_failed)
    } finally {
      setBusy(false)
    }
  }

  const label = 'w-[7.4rem] shrink-0 border-r border-rule bg-paper px-3 py-3 text-[0.9rem] leading-snug text-rule2 sm:w-[8rem]'
  return (
    <form onSubmit={submit} className="ruled-strong bg-field" noValidate>
      <div className="flex items-baseline justify-between border-b-[1.5px] border-rule2 px-4 py-3">
        <h2 className="cond text-[1.6rem] font-bold">{t.form_title}</h2>
        <span className="text-sm text-rule2">
          {t.serial} <span className="num font-mono text-cinnabar">{serial}</span>
        </span>
      </div>

      <label className="flex rule-b">
        <span className={label}>{t.nickname}</span>
        <input className="w-full bg-transparent px-3 py-3 outline-none focus:bg-sheet" value={nickname} maxLength={24} placeholder={t.nickname_ph} onChange={(e) => setNickname(e.target.value)} />
      </label>
      <label className="flex rule-b">
        <span className={label}>{t.address}</span>
        <span className="w-full">
          <input className="w-full bg-transparent px-3 pt-3 font-mono text-[0.9rem] outline-none focus:bg-sheet" value={address} placeholder="0x…" spellCheck={false} autoCapitalize="off" onChange={(e) => setAddress(e.target.value)} />
          <span className="block px-3 pb-2 text-xs text-ink2">{t.address_hint}</span>
        </span>
      </label>

      <fieldset className="rule-b px-4 py-3">
        <legend className="sr-only">{t.agent_pick}</legend>
        <p className="mb-2 text-[0.9rem] text-rule2">{t.agent_pick}</p>
        <div className="grid grid-cols-2 gap-2">
          {(['guarded', 'naive'] as const).map((k) => (
            <label key={k} className={`cursor-pointer rounded-box border p-2.5 ${agent === k ? 'border-ink bg-sheet shadow-[inset_0_0_0_1px_var(--ink)]' : 'border-rule'}`}>
              <input type="radio" name="agent" value={k} checked={agent === k} onChange={() => setAgent(k)} className="sr-only" />
              <span className="block font-semibold">{k === 'guarded' ? t.agent_guarded : t.agent_naive}</span>
              <span className="mt-0.5 block text-[0.82rem] leading-snug text-ink2">{k === 'guarded' ? t.agent_guarded_hint : t.agent_naive_hint}</span>
            </label>
          ))}
        </div>
        {agent === 'naive' && <p className="mt-2 text-[0.82rem] text-ink">{t.naive_disclosure}</p>}
      </fieldset>

      <div className="px-4 py-3">
        <div className="mb-2.5 flex gap-1" role="tablist">
          {(['upload', 'message'] as const).map((m) => (
            <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => setMode(m)} className={`rounded-box px-3 py-1.5 text-[0.92rem] ${mode === m ? 'bg-ink text-field' : 'text-ink hover:bg-paper'}`}>
              {m === 'upload' ? t.tab_upload : t.tab_message}
            </button>
          ))}
        </div>
        {mode === 'upload' ? (
          <div>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,application/pdf" className="sr-only" id="cs-file" onChange={(e) => void pick(e.target.files?.[0] ?? null)} />
            <label htmlFor="cs-file" className="flex min-h-[6.5rem] cursor-pointer flex-col items-center justify-center rounded-box border border-dashed border-rule2 bg-sheet px-3 py-4 text-center hover:bg-paper">
              {shrinking ? (
                <span className="step-live font-semibold">{t.upload_shrinking}</span>
              ) : file ? (
                <span className="break-all font-mono text-sm">
                  {file.name} <span className="text-ink2">({kb(file.size)})</span>
                </span>
              ) : (
                <span className="font-semibold">{t.upload_cta}</span>
              )}
              <span className="mt-1 text-xs text-ink2">{t.upload_hint}</span>
            </label>
          </div>
        ) : (
          <textarea className="field min-h-[7rem] resize-y" maxLength={4000} placeholder={t.message_ph} value={text} onChange={(e) => setText(e.target.value)} />
        )}
        {error && (
          <p role="alert" className="mt-2 text-sm font-semibold text-cinnabar">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn-ink mt-3 w-full py-3 text-[1.05rem]" disabled={busy || shrinking}>
          {busy ? t.submitting : t.submit}
        </button>
      </div>
    </form>
  )
}

function Result({ id, onAgain }: { id: string; onAgain: () => void }) {
  const { t, lang } = useLang()
  const q = useQuery({
    queryKey: ['attempt', id],
    queryFn: () => api.attempt(id),
    refetchInterval: (query) => {
      const d = query.state.data as Attempt | undefined
      return d && (d.status === 'done' || d.status === 'error') ? false : 1000
    },
  })
  const a = q.data
  const done = a && (a.status === 'done' || a.status === 'error')
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  const kind = !a?.outcome ? null : a.outcome
  const explain = () => {
    if (!a) return ''
    if (a.outcome === 'refused') return t.explain_refused
    if (a.outcome === 'blocked') return t.explain_blocked
    if (a.outcome === 'paid') return t.explain_paid_fake
    if (a.outcome === 'no_invoice') return t.explain_no_invoice
    return t.explain_error
  }

  return (
    <div ref={ref} className="ruled-strong scroll-mt-4 bg-field p-4">
      {a ? <StepRow steps={a.steps} /> : <div className="h-28 animate-pulse rounded-box bg-paper2" />}

      {done && kind && (
        <div className="mt-5 grid grid-cols-[auto_1fr] items-center gap-4">
          <Seal kind={kind} size={132} />
          <div>
            <p className="cond text-[1.9rem] font-extrabold leading-tight" style={{ color: kind === 'paid' ? 'var(--jade)' : kind === 'blocked' ? 'var(--cinnabar)' : 'var(--ink)' }}>
              {kind === 'paid' ? t.outcome_paid : kind === 'blocked' ? t.outcome_blocked : kind === 'refused' ? t.outcome_refused : kind === 'no_invoice' ? t.outcome_no_invoice : t.outcome_error}
            </p>
            <p className="mt-1 text-[0.95rem] leading-snug">
              {explain()}
              {a.outcome === 'blocked' && (
                <>
                  {lang === 'zh' ? '' : ' '}
                  <strong>{lang === 'zh' ? a.tx?.reason_label_zh ?? reasonLabel(a.tx?.reason, 'zh') : a.tx?.reason_label_en ?? reasonLabel(a.tx?.reason, 'en')}</strong>
                  {lang === 'zh' ? '。' : '.'}
                </>
              )}
            </p>
            {a.tx && (
              <p className="mt-2 text-sm">
                <TxLink href={a.tx.explorer_url} hash={a.tx.hash} label={t.view_tx} />
                {a.tx.network === 'testnet' && <span className="ml-2 text-xs text-ink2">{lang === 'zh' ? '测试网' : 'testnet'}</span>}
              </p>
            )}
          </div>
        </div>
      )}

      {done && a && a.flags.length > 0 && (
        <div className="mt-5">
          <h3 className="cond text-lg font-bold">{t.flags_title}</h3>
          <ul className="mt-1.5 space-y-1.5">
            {a.flags.map((f) => (
              <li key={f.code} className="flex gap-2 text-[0.92rem] leading-snug">
                <span className="mt-[0.45rem] h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: f.severity === 'high' ? 'var(--cinnabar)' : 'var(--ink-2)' }} aria-hidden />
                <span>
                  <strong>{flagLabel(f.code, lang)}.</strong> {lang === 'zh' ? f.detail_zh : f.detail_en}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {done && (
        <button type="button" className="btn btn-line mt-5 w-full" onClick={onAgain}>
          {t.try_again}
        </button>
      )}
    </div>
  )
}
