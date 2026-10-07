import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { QRCodeSVG } from 'qrcode.react'
import { api } from '../api/client'
import type { AgentKind, AppConfig, LedgerEvent, LedgerKind } from '../api/types'
import { useLang } from '../i18n'
import type { Strings } from '../i18n/strings'
import { Header } from '../components/Header'
import { WalletScreeningPanel } from '../components/WalletScreening'
import { ReputationPanel } from '../components/Reputation'
import { Icon } from '../components/Icon'
import { Counters } from '../components/Counters'
import { BrandSeal, Seal, SealMark } from '../components/Seal'
import { Address, EvalCard, TxLink } from '../components/bits'
import { LangSwitch, ThemeSwitch } from '../components/Toggles'
import { addressUrl, bountyUrl, clock, fmtAmount, shortAddr, timeAgo } from '../lib/format'
import { reasonLabel } from '../lib/reasons'

type Lang = 'zh' | 'en'

const markFor = (e: LedgerEvent): 'paid' | 'blocked' | 'change' => (e.name === 'Paid' ? 'paid' : e.name === 'Blocked' ? 'blocked' : 'change')

function eventLabel(e: LedgerEvent, t: Strings): string {
  if (e.name === 'Paid') return t.outcome_paid
  if (e.name === 'Blocked') return t.outcome_blocked
  return t[`ev_${e.name}` as keyof Strings] as string
}

function eventReason(e: LedgerEvent, lang: Lang): string {
  if (e.name !== 'Blocked') return ''
  return (lang === 'zh' ? e.reason_label_zh : e.reason_label_en) ?? reasonLabel(e.reason, lang)
}

function agentLabel(a: AgentKind | null, lang: Lang): string {
  if (!a) return ''
  if (lang === 'zh') return a === 'guarded' ? '带防护' : '裸奔'
  return a === 'guarded' ? 'Guarded' : 'Naive'
}

function useViewportHeight() {
  const [h, setH] = useState(() => window.innerHeight)
  useEffect(() => {
    const on = () => setH(window.innerHeight)
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  }, [])
  return h
}

/** Ids that arrived after the first load, so new rows can be marked as they land. */
function useArrivals(events: LedgerEvent[] | undefined) {
  const seen = useRef<Set<string> | null>(null)
  const [fresh, setFresh] = useState<Set<string>>(new Set())
  const [latest, setLatest] = useState<LedgerEvent | null>(null)
  useEffect(() => {
    if (!events) return
    if (seen.current === null) {
      seen.current = new Set(events.map((e) => e.id))
      return
    }
    const added = events.filter((e) => !seen.current!.has(e.id))
    if (added.length === 0) return
    added.forEach((e) => seen.current!.add(e.id))
    setFresh(new Set(added.map((e) => e.id)))
    const money = added.find((e) => e.name === 'Paid' || e.name === 'Blocked')
    if (money) setLatest(money)
  }, [events])
  const clearLatest = useCallback(() => setLatest(null), [])
  return { fresh, latest, clearLatest }
}

export default function LedgerPage() {
  const { t, tr } = useLang()
  const [params, setParams] = useSearchParams()
  const stage = params.get('stage') === '1'
  const [kind, setKind] = useState<LedgerKind>('all')

  const config = useQuery({ queryKey: ['config'], queryFn: api.config, staleTime: 60_000 })
  const stats = useQuery({ queryKey: ['stats'], queryFn: api.stats, refetchInterval: 3000 })
  const evalq = useQuery({ queryKey: ['eval'], queryFn: api.evalResults, refetchInterval: 30_000 })
  // stage mode always watches everything; the table follows the filter tabs
  const ledger = useQuery({ queryKey: ['ledger', stage ? 'all' : kind], queryFn: () => api.ledger(stage ? 'all' : kind, 100), refetchInterval: 2500 })

  const setStage = useCallback(
    (on: boolean) => {
      const next = new URLSearchParams(params)
      if (on) next.set('stage', '1')
      else next.delete('stage')
      setParams(next, { replace: true })
      try {
        if (on && !document.fullscreenElement) void document.documentElement.requestFullscreen?.()
        if (!on && document.fullscreenElement) void document.exitFullscreen?.()
      } catch {
        /* fullscreen not allowed here; stage mode still works */
      }
    },
    [params, setParams],
  )

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'f' || e.key === 'F') setStage(!stage)
      if (e.key === 'Escape' && stage) setStage(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [stage, setStage])

  const symbol = config.data?.token.symbol ?? ''
  const qr = bountyUrl(config.data?.public_base_url)

  if (stage) return <Stage config={config.data} stats={stats.data} events={ledger.data} evalData={evalq.data} qr={qr} onExit={() => setStage(false)} />

  return (
    <div className="workspace">
      <Header />
      <main tabIndex={-1} className="page-content ">
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
          <div>
            <h1 className="cond text-[2.4rem] font-extrabold leading-tight sm:text-[2.9rem]">{t.ledger_title}</h1>
            <p className="max-w-[38rem] text-ink2">{t.ledger_sub}</p>
          </div>
          {config.data && <ContractLine config={config.data} />}
        </div>

        <div className="mt-7">
          <Counters stats={stats.data?.outside} symbol={symbol} />
          <p className="mt-3 text-xs text-ink2">{t.c_lost}: {t.money_lost_note}. {stats.data && stats.data.seed.attempts > 0 && t.c_seed_note.replace('{n}', String(stats.data.seed.attempts))}</p>
        </div>
        <div className="mt-7 grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_280px]">
          <div className="grid gap-5"><ReputationPanel /><WalletScreeningPanel /></div>
          <aside className="grid gap-5 sm:grid-cols-2 xl:grid-cols-1"><QrCard url={qr} /><EvalCard data={evalq.data} /></aside>
        </div>
        <div className="mb-4 mt-9 flex items-center gap-2"><Icon name="activity" size={19} /><h2 className="text-lg font-semibold">{tr('Recent activity', '最近记录')}</h2></div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="tab-scroll flex gap-1" role="tablist" aria-label={t.ledger_title}>
            {(
              [
                ['all', t.filter_all],
                ['paid', t.filter_paid],
                ['blocked', t.filter_blocked],
                ['changes', t.filter_changes],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                type="button"
                role="tab"
                aria-selected={kind === k}
                onClick={() => setKind(k)}
                className={`rounded-box px-3 py-1.5 text-[0.95rem] ${kind === k ? 'bg-ink text-field' : 'text-ink hover:bg-paper2'}`}
              >
                {label}
              </button>
            ))}
          </div>
          <button type="button" className="btn btn-line hidden py-1.5 text-[0.95rem] md:inline-flex" onClick={() => setStage(true)}>
            {t.stage_on}
            <kbd className="rounded-[2px] border border-ink2 px-1 font-mono text-xs text-ink2">F</kbd>
          </button>
        </div>

        <EventsTable events={ledger.data} loading={ledger.isLoading} symbol={symbol} netOf={config.data?.network} />
      </main>
    </div>
  )
}

function ContractLine({ config }: { config: AppConfig }) {
  const { tr } = useLang()
  const net = config.network === 'mainnet' ? tr('BOT Chain mainnet', 'BOT Chain 主网') : tr('BOT Chain testnet', 'BOT Chain 测试网')
  return (
    <p className="text-sm text-ink2">
      {net} ({config.chain_id}), {tr('contract', '合约')}{' '}
      <a href={addressUrl(config.explorer_url, config.contract_address)} target="_blank" rel="noreferrer" className="font-mono text-ink underline decoration-rule underline-offset-4 hover:decoration-ink" title={config.contract_address}>
        {shortAddr(config.contract_address, 8, 6)}
      </a>
    </p>
  )
}

function QrCard({ url, big = false, qrSize }: { url: string; big?: boolean; qrSize?: number }) {
  const { t } = useLang()
  if (!url) return null
  const shown = url.replace(/^https?:\/\//, '')
  if (big)
    return (
      <section className="ruled bg-field p-[clamp(1rem,2.2vh,1.5rem)]">
        <div className="mx-auto w-fit bg-[#fff] p-3 ruled">
          <QRCodeSVG value={url} size={qrSize ?? 280} bgColor="#ffffff" fgColor="#1d2836" level="M" marginSize={0} />
        </div>
        <p className="cond keep mt-3 text-center text-[clamp(1.5rem,3.4vh,2.2rem)] font-bold leading-tight">{t.scan_to_try}</p>
        <p className="mt-1 break-all text-center font-mono text-base text-ink2">{shown}</p>
      </section>
    )
  return (
    <section className="flex items-center gap-4 ruled bg-field p-4">
      <div className="w-fit shrink-0 bg-[#fff] p-2 ruled">
        <QRCodeSVG value={url} size={104} bgColor="#ffffff" fgColor="#1d2836" level="M" marginSize={0} />
      </div>
      <div className="min-w-0">
        <p className="keep text-base font-semibold leading-tight">{t.scan_to_try}</p>
        <p className="mt-1 break-all font-mono text-xs text-ink2">{shown}</p>
      </div>
    </section>
  )
}

/** Marks rows from the other network when bounty and team transactions live on different chains. */
function NetTag({ net }: { net: 'mainnet' | 'testnet' }) {
  const { tr } = useLang()
  return <span className="ml-1.5 rounded-[2px] border border-dashed border-ink2 px-1 py-px text-[0.7rem] text-ink2">{net === 'testnet' ? tr('testnet', '测试网') : tr('mainnet', '主网')}</span>
}

function EventsTable({ events, loading, symbol, netOf }: { events?: LedgerEvent[]; loading: boolean; symbol: string; netOf?: 'mainnet' | 'testnet' }) {
  const { t, lang } = useLang()
  const { fresh } = useArrivals(events)
  if (loading) return <div className="mt-3 h-64 animate-pulse rounded-box bg-paper2" aria-hidden />
  if (!events || events.length === 0) return <p className="mt-6 text-ink2">{t.ledger_empty}</p>

  return (
    <>
      {/* desktop: a ruled ledger page */}
      <div className="mt-3 hidden overflow-x-auto ruled bg-field md:block">
        <table className="w-full min-w-[760px] border-collapse text-left text-[0.95rem]">
          <thead>
            <tr className="rule-b bg-paper text-[0.85rem] text-rule2">
              <th className="w-[6.5rem] px-3 py-2 font-normal">{t.col_time}</th>
              <th className="w-[9rem] px-3 py-2 font-normal">{t.col_event}</th>
              <th className="px-3 py-2 font-normal">{t.col_vendor}</th>
              <th className="w-[8.5rem] px-3 py-2 text-right font-normal">{t.col_amount}</th>
              <th className="w-[6.5rem] px-3 py-2 font-normal">{t.col_agent}</th>
              <th className="w-[12rem] px-3 py-2 font-normal">{t.col_reason}</th>
              <th className="w-[8.5rem] px-3 py-2 font-normal">{t.col_tx}</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => {
              const mark = markFor(e)
              return (
                <tr key={e.id} className={`rule-b align-top last:border-b-0 ${fresh.has(e.id) ? 'row-new' : ''}`}>
                  <td className="num px-3 py-2.5 font-mono text-[0.85rem] text-ink2" title={e.block_time}>
                    {clock(e.block_time)}
                  </td>
                  <td className="px-3 py-2">
                    <span className="flex items-center gap-2">
                      <SealMark kind={mark} size={28} />
                      <span className="font-semibold" style={{ color: mark === 'paid' ? 'var(--jade)' : mark === 'blocked' ? 'var(--cinnabar)' : 'var(--ink)' }}>
                        {eventLabel(e, t)}
                      </span>
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    {mark === 'change' ? (
                      <span>{(lang === 'zh' ? e.summary_zh : e.summary_en) ?? eventLabel(e, t)}</span>
                    ) : (
                      <>
                        <span className="block leading-snug">{e.vendor_name ?? '—'}</span>
                        {e.pay_to && (
                          <span className="text-[0.82rem] text-ink2">
                            {lang === 'zh' ? '付到 ' : 'to '}
                            <Address value={e.pay_to} className={e.reason === 'PayoutMismatch' || e.reason === 'UnknownVendor' ? 'text-cinnabar' : ''} />
                          </span>
                        )}
                      </>
                    )}
                  </td>
                  <td className="num px-3 py-2.5 text-right font-mono">
                    {e.amount ? (
                      <>
                        {fmtAmount(e.amount)} <span className="text-[0.8rem] text-ink2">{symbol}</span>
                      </>
                    ) : (
                      <span className="text-ink2">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-ink2">
                    {agentLabel(e.agent, lang) || '—'}
                    {e.network && e.network !== netOf && <NetTag net={e.network} />}
                  </td>
                  <td className="px-3 py-2.5">{eventReason(e, lang) || <span className="text-ink2">—</span>}</td>
                  <td className="px-3 py-2.5">
                    <TxLink href={e.explorer_url} hash={e.tx_hash} label={shortAddr(e.tx_hash, 6, 4)} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* phone: one slip per event */}
      <ol className="mt-3 divide-y divide-rule ruled bg-field md:hidden">
        {events.map((e) => {
          const mark = markFor(e)
          return (
            <li key={e.id} className={`grid grid-cols-[auto_1fr_auto] gap-x-3 px-3 py-2.5 ${fresh.has(e.id) ? 'row-new' : ''}`}>
              <SealMark kind={mark} size={30} />
              <div className="min-w-0">
                <p className="font-semibold leading-snug" style={{ color: mark === 'paid' ? 'var(--jade)' : mark === 'blocked' ? 'var(--cinnabar)' : 'var(--ink)' }}>
                  {eventLabel(e, t)}
                  {eventReason(e, lang) && <span className="font-normal text-ink">: {eventReason(e, lang)}</span>}
                </p>
                <p className="truncate text-[0.9rem] text-ink2">
                  {mark === 'change' ? (lang === 'zh' ? e.summary_zh : e.summary_en) : [e.vendor_name, agentLabel(e.agent, lang)].filter(Boolean).join(lang === 'zh' ? '，' : ', ')}
                </p>
              </div>
              <div className="text-right">
                {e.amount && <p className="num font-mono text-[0.95rem]">{fmtAmount(e.amount)}</p>}
                <a href={e.explorer_url} target="_blank" rel="noreferrer" className="text-xs text-ink2 underline decoration-rule underline-offset-2">
                  {timeAgo(e.block_time, lang)}
                </a>
              </div>
            </li>
          )
        })}
      </ol>
    </>
  )
}

/** The projector view: readable from the back of a room, with the QR code big enough to scan from a seat. */
function Stage({
  config,
  stats,
  events,
  evalData,
  qr,
  onExit,
}: {
  config?: AppConfig
  stats?: import('../api/types').Stats
  events?: LedgerEvent[]
  evalData?: import('../api/types').EvalResults
  qr: string
  onExit: () => void
}) {
  const { t, lang } = useLang()
  const symbol = config?.token.symbol ?? ''
  const { fresh, latest, clearLatest } = useArrivals(events)
  const h = useViewportHeight()
  const rows = h >= 1000 ? 6 : h >= 860 ? 5 : h >= 700 ? 4 : 3
  const qrSize = Math.round(Math.max(170, Math.min(window.innerWidth >= 1280 ? 300 : 230, h * 0.27)))
  const recent = useMemo(() => (events ?? []).filter((e) => e.name === 'Paid' || e.name === 'Blocked' || e.name === 'ChangeQueued' || e.name === 'ChangeExecuted').slice(0, rows), [events, rows])

  // a fresh payment or block stamps a big seal for a few seconds
  useEffect(() => {
    if (!latest) return
    const timer = setTimeout(clearLatest, 3200)
    return () => clearTimeout(timer)
  }, [latest, clearLatest])

  return (
    <div className="flex min-h-dvh flex-col bg-paper">
      <div className="guilloche rule-b">
        <div className="flex items-center gap-3 px-8 py-3">
          <BrandSeal size={40} />
          <span className="cond text-[1.7rem] font-bold leading-none">Countersign</span>
          {api.mode === 'mock' && <span className="mock-pill">{t.mock_badge}</span>}
          <span className="ml-3 text-lg text-ink2">{t.tagline}</span>
          <div className="ml-auto flex items-center gap-2">
            <LangSwitch size="lg" />
            <ThemeSwitch />
            <button type="button" onClick={onExit} className="rounded-box px-2.5 py-1 text-sm text-ink2 hover:bg-paper2">
              {t.stage_off} <kbd className="font-mono text-xs">Esc</kbd>
            </button>
          </div>
        </div>
      </div>

      <div className="grid flex-1 gap-[clamp(1rem,3vh,2rem)] px-8 py-[clamp(0.75rem,2.2vh,1.5rem)] lg:grid-cols-[1fr_21rem] xl:grid-cols-[1fr_27rem]">
        <div className="flex min-w-0 flex-col gap-[clamp(0.75rem,2.4vh,1.5rem)]">
          <Counters stats={stats?.outside} symbol={symbol} size="stage" />

          <section className="relative">
            <h2 className="cond mb-2 text-2xl font-bold">{t.latest_onchain}</h2>
            <ol className="divide-y divide-rule ruled bg-field">
              {recent.length === 0 && <li className="px-5 py-6 text-xl text-ink2">{t.ledger_empty}</li>}
              {recent.map((e) => {
                const mark = markFor(e)
                const color = mark === 'paid' ? 'var(--jade)' : mark === 'blocked' ? 'var(--cinnabar)' : 'var(--ink)'
                return (
                  <li key={e.id} className={`grid grid-cols-[auto_11rem_1fr_auto] items-center gap-x-5 px-5 py-[clamp(0.4rem,1.3vh,0.8rem)] ${fresh.has(e.id) ? 'row-new' : ''}`}>
                    <span className={fresh.has(e.id) ? 'seal-stamp' : ''} style={{ ['--seal-rot' as string]: '0deg' }}>
                      <SealMark kind={mark} size={46} />
                    </span>
                    <span className="cond text-[1.75rem] font-bold leading-none" style={{ color }}>
                      {eventLabel(e, t)}
                    </span>
                    <span className="min-w-0 truncate text-[1.35rem]">
                      {mark === 'change' ? (lang === 'zh' ? e.summary_zh : e.summary_en) : eventReason(e, lang) || e.vendor_name}
                      {mark !== 'change' && e.agent && <span className="ml-3 text-lg text-ink2">{agentLabel(e.agent, lang)}</span>}
                    </span>
                    <span className="text-right">
                      {e.amount && (
                        <span className="num cond block text-[1.6rem] font-bold leading-none">
                          {fmtAmount(e.amount)} <span className="text-base font-semibold text-ink2">{symbol}</span>
                        </span>
                      )}
                      <span className="text-sm text-ink2">{timeAgo(e.block_time, lang)}</span>
                    </span>
                  </li>
                )
              })}
            </ol>
            {latest && (
              <div className="pointer-events-none absolute -top-8 right-[34%]" aria-live="polite">
                <Seal kind={latest.name === 'Paid' ? 'paid' : 'blocked'} size={Math.round(Math.max(170, Math.min(240, h * 0.22)))} rotate={-11} />
              </div>
            )}
          </section>
        </div>

        <aside className="flex flex-col gap-6">
          <QrCard url={qr} big qrSize={qrSize} />
          <EvalCard data={evalData} large />
        </aside>
      </div>
    </div>
  )
}
