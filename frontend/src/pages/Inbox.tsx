import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api, AuthError, clearAdminToken, getAdminToken } from '../api/client'
import { useAuth } from '../lib/auth'
import type { AgentKind, Attempt, BatchSummary, DemoInvoice, Source } from '../api/types'
import { useLang } from '../i18n'
import { Icon } from '../components/Icon'
import { Header } from '../components/Header'
import { Seal, SealMark } from '../components/Seal'
import { StepRow } from '../components/StepRow'
import { InvoicePreview } from '../components/InvoicePreview'
import { Decision } from '../components/Decision'
import { AdminGate, Address, TxLink } from '../components/bits'
import { attemptMark, isDone, outcomeLabel, outcomeReason, secs, stepMs } from '../lib/attempt'
import { clock, fmtAmount } from '../lib/format'
import { flagLabel } from '../lib/reasons'
import { prepareUpload } from '../lib/upload'

type Target = AgentKind | 'both'
type Pair = { guarded: string; naive: string; label: string }

/** Sends one invoice (a file or a demo invoice) to one agent or to both. */
async function sendTo(target: Target, what: { file?: File; demo?: string }) {
  const one = (agent: AgentKind) => api.submitTeam({ nickname: 'team', agent, ...what }).then((r) => r.attempt_id)
  if (target !== 'both') return { ids: [await one(target)], pair: null }
  const [g, n] = await Promise.all([one('guarded'), one('naive')])
  return { ids: [g, n], pair: { guarded: g, naive: n } }
}

export default function InboxPage() {
  return (
    <div className="workspace">
      <Header />
      <AdminGate>
        <Inbox />
      </AdminGate>
    </div>
  )
}

function Inbox() {
  const { tr } = useLang()
  const { refresh } = useAuth()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [target, setTarget] = useState<Target>('both')
  const [source, setSource] = useState<Source | 'all'>('all')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const [pair, setPair] = useState<Pair | null>(null)
  const [batchId, setBatchId] = useState<string | null>(null)

  const onSent = (ids: string[], p: { guarded: string; naive: string } | null, label: string) => {
    void qc.invalidateQueries({ queryKey: ['team-attempts'] })
    setSource('all')
    if (p) {
      setPair({ ...p, label })
      setSelected(null)
    } else if (ids[0]) {
      setPair(null)
      setSelected(ids[0])
    }
  }

  const list = useQuery({
    queryKey: ['team-attempts', source],
    queryFn: () => api.teamAttempts(source, 200),
    refetchInterval: (q) => {
      const d = q.state.data as Attempt[] | undefined
      return d?.some((a) => !isDone(a)) ? 1200 : 5000
    },
    retry: (n, err) => !(err instanceof AuthError) && n < 2,
  })
  const config = useQuery({ queryKey: ['config'], queryFn: api.config, staleTime: 60_000 })
  const symbol = config.data?.token.symbol ?? ''

  if (list.error instanceof AuthError) {
    return (
      <div className="mx-auto mt-16 max-w-sm px-4">
        <p className="font-semibold text-cinnabar">{tr('Your session ended or the access was rejected.', '登录已失效或访问被拒绝。')}</p>
        <button
          type="button"
          className="btn btn-line mt-3"
          onClick={() => {
            clearAdminToken()
            qc.clear()
            void refresh().then(() => navigate('/login?next=/inbox', { replace: true }))
          }}
        >
          {tr('Sign in again', '重新登录')}
        </button>
      </div>
    )
  }

  const attempts = list.data ?? []
  const shown = attempts.filter(a => [a.file_name, a.extraction?.invoice_number, a.proposal?.vendor_name, a.agent].some(value => value?.toLowerCase().includes(search.toLowerCase())))
  const current = attempts.find((a) => a.id === selected) ?? null

  return (
    <main tabIndex={-1} className="page-content ">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="cond text-[2.4rem] font-extrabold leading-tight">{tr('Inbox', '收件箱')}</h1>
          <p className="mt-2 text-sm text-ink2">{tr('Read an invoice. Compare the agents. Follow every decision.', '读取发票，对照 Agent，追踪每一步决定。')}</p>
        </div>
        <AgentSwitch value={target} onChange={setTarget} />
      </div>

      <dl className="metric-grid mt-7">
        {[
          { label: tr('Invoices in view', '当前发票'), value: attempts.length, icon: 'inbox' as const },
          { label: tr('Paid', '已支付'), value: attempts.filter(a => a.outcome === 'paid').length, icon: 'check' as const },
          { label: tr('Needs review', '需要检查'), value: attempts.filter(a => ['refused', 'blocked', 'error'].includes(a.outcome ?? '')).length, icon: 'flag' as const },
          { label: tr('Processing', '处理中'), value: attempts.filter(a => !isDone(a)).length, icon: 'activity' as const },
        ].map(x => <div className="metric-card" key={x.label}><dt>{x.label}<Icon name={x.icon} size={17} /></dt><dd>{list.isLoading ? '—' : x.value}</dd></div>)}
      </dl>
      <Roles />
      <DemoShelf target={target} onSent={onSent} />

      {/* the clean batch spends the shared AI budget, so only the team token runs it */}
      <div className={`mt-4 grid gap-4 ${getAdminToken() ? 'md:grid-cols-[1fr_20rem]' : ''}`}>
        <DropZone target={target} onSent={onSent} />
        {getAdminToken() && <BatchBox
          batchId={batchId}
          onStart={async () => {
            const r = await api.runBatch()
            setBatchId(r.batch_id)
            setSource('all')
          }}
        />}
      </div>

      {pair && <Compare pair={pair} attempts={attempts} symbol={symbol} onOpen={setSelected} onClose={() => setPair(null)} />}

      <div className="mt-8 flex flex-wrap items-center justify-between gap-2">
        <div className="tab-scroll flex gap-1" role="tablist" aria-label={tr('Source', '来源')}>
          {(
            [
              ['all', tr('All', '全部')],
              ['team', tr('Team', '团队')],
              ['batch', tr('Clean batch', '正常批次')],
              ['bounty', tr('Bounty', '挑战')],
              ['seed', tr('Seed set', '测试样本')],
            ] as const
          ).map(([k, label]) => (
            <button key={k} type="button" role="tab" aria-selected={source === k} onClick={() => setSource(k)} className={`rounded-box px-3 py-1.5 text-[0.95rem] ${source === k ? 'bg-ink text-field' : 'hover:bg-paper2'}`}>
              {label}
            </button>
          ))}
        </div>
        <label className="flex w-full items-center gap-2 rounded-box border border-rule bg-field px-3 py-2 sm:w-64"><Icon name="search" size={16} className="text-ink2" /><input className="min-w-0 w-full bg-transparent text-sm" aria-label={tr('Search invoices', '搜索发票')} placeholder={tr('Search invoices…', '搜索发票…')} value={search} onChange={e => setSearch(e.target.value)} /></label>
      </div>

      <div className={`mt-3 grid gap-5 ${current ? 'lg:grid-cols-[minmax(0,1fr)_34rem]' : ''}`}>
        <AttemptsTable attempts={search ? shown : attempts} loading={list.isLoading} selected={selected} onSelect={setSelected} symbol={symbol} compact={!!current} />
        {current && <Drawer attempt={current} symbol={symbol} onClose={() => setSelected(null)} />}
      </div>
    </main>
  )
}

function AgentSwitch({ value, onChange }: { value: Target; onChange: (a: Target) => void }) {
  const { tr } = useLang()
  const opts: Array<[Target, string]> = [
    ['both', tr('Both agents', '两个都发')],
    ['guarded', tr('Guarded', '带防护')],
    ['naive', tr('Naive', '裸奔')],
  ]
  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-ink2">{tr('Send to', '发给')}</span>
      <div className="flex overflow-hidden ruled bg-field" role="radiogroup" aria-label={tr('Send to', '发给')}>
        {opts.map(([k, label], i) => (
          <button key={k} type="button" role="radio" aria-checked={value === k} onClick={() => onChange(k)} className={`px-3 py-1.5 text-[0.95rem] ${value === k ? 'bg-ink text-field' : 'hover:bg-paper2'} ${i ? 'border-l border-rule' : ''}`}>
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}

// one column on phones, 2×2 on tablets, one row on wide screens
const ROLE_BORDERS = ['', 'border-t sm:border-l sm:border-t-0', 'border-t xl:border-l xl:border-t-0', 'border-t sm:border-l xl:border-t-0']

/** The split of responsibility, stated once above the demo: the agent proposes, the contract decides. */
function Roles() {
  const { tr } = useLang()
  const steps = [
    [tr('Invoice arrives', '发票进来'), tr('A PDF, an image or typed text.', 'PDF、图片或一段文字。')],
    [tr('AI agent proposes', 'AI Agent 提议'), tr('Reads the invoice, flags tricks, and asks the vault to pay. It holds no funds.', '读发票、标出可疑内容，再向金库请求付款。它手里没有钱。')],
    [tr('Vault contract decides', '金库合约拍板'), tr('Checks the vendor registry, payout address, PO budget, duplicates and the daily cap.', '核对供应商登记、收款地址、采购单预算、重复发票和每日限额。')],
    [tr('Paid or blocked on chain', '链上付款或拒付'), tr('Either way, the transaction on BOT Chain is the receipt.', '无论结果如何，BOT Chain 上的交易就是回执。')],
  ]
  return (
    <ol className="mt-5 grid overflow-hidden ruled bg-field sm:grid-cols-2 xl:grid-cols-4" aria-label={tr('How a payment is decided', '付款如何决定')}>
      {steps.map(([title, text], i) => (
        <li key={title} className={`border-rule p-3 ${ROLE_BORDERS[i]}`}>
          <p className="text-xs font-semibold text-rule2">0{i + 1}</p>
          <p className="font-semibold">{title}</p>
          <p className="mt-0.5 text-[0.85rem] leading-snug text-ink2">{text}</p>
        </li>
      ))}
    </ol>
  )
}

const targetName = (t: Target, tr: (e: string, z: string) => string) =>
  t === 'both' ? tr('both agents', '两个 Agent') : t === 'guarded' ? tr('the guarded agent', '带防护的 Agent') : tr('the naive agent', '裸奔 Agent')

type OnSent = (ids: string[], pair: { guarded: string; naive: string } | null, label: string) => void

/** The invoices we use on stage, one click each. */
function DemoShelf({ target, onSent }: { target: Target; onSent: OnSent }) {
  const { tr, lang } = useLang()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['demo-invoices'], queryFn: api.demoInvoices, staleTime: 60_000, retry: 1 })
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  if (!q.data || q.data.length === 0) return null
  // a clean invoice can be paid once; sending it to both agents would make the second a duplicate
  const routeFor = (p: DemoInvoice): Target => (p.kind === 'clean' && target === 'both' ? 'guarded' : target)

  async function run(p: DemoInvoice) {
    setErr(null)
    setBusy(p.name)
    try {
      const r = await sendTo(routeFor(p), { demo: p.name })
      onSent(r.ids, r.pair, lang === 'zh' ? p.title_zh : p.title_en)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
      void qc.invalidateQueries({ queryKey: ['demo-invoices'] })
    }
  }

  return (
    <section className="mt-5" aria-label={tr('Demo invoices', '演示发票')}>
      <h2 className="mb-3 mt-7 text-base font-semibold">{tr('Try a demo scenario', '试试演示场景')}</h2>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {q.data.map((p) => (
          <li key={p.name}>
            <button
              type="button"
              onClick={() => void run(p)}
              disabled={busy !== null}
              className="flex h-full w-full flex-col items-start rounded-box border border-rule bg-field p-3 text-left hover:border-ink hover:bg-sheet disabled:opacity-60"
            >
              <span className={`text-xs font-semibold ${p.kind === 'clean' ? 'text-jade' : 'text-cinnabar'}`}>{p.kind === 'clean' ? tr('clean', '正常') : tr('poisoned', '有毒')}</span>
              <span className="mt-0.5 font-semibold leading-snug">{lang === 'zh' ? p.title_zh : p.title_en}</span>
              {(p.note_en || p.note_zh) && <span className="mt-0.5 text-[0.82rem] leading-snug text-ink2">{lang === 'zh' ? p.note_zh : p.note_en}</span>}
              <span className="mt-auto pt-2 text-sm text-ink2">{busy === p.name ? tr('Sending…', '发送中…') : `${tr('Run on', '发给')} ${targetName(routeFor(p), tr)}`}</span>
            </button>
          </li>
        ))}
      </ul>
      {err && <p role="alert" className="mt-2 text-sm font-semibold text-cinnabar">{err}</p>}
    </section>
  )
}

function DropZone({ target, onSent }: { target: Target; onSent: OnSent }) {
  const { tr } = useLang()
  const [over, setOver] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)

  async function send(files: File[]) {
    setErr(null)
    let first: { ids: string[]; pair: { guarded: string; naive: string } | null; label: string } | null = null
    const skipped: string[] = []
    try {
      for (let i = 0; i < files.length; i++) {
        setBusy(tr(`Sending ${i + 1} of ${files.length}…`, `正在发送第 ${i + 1}/${files.length} 个…`))
        let f: File
        try {
          f = await prepareUpload(files[i])
        } catch {
          skipped.push(files[i].name)
          continue
        }
        const r = await sendTo(target, { file: f })
        first ??= { ...r, label: f.name }
      }
      if (skipped.length) setErr(tr(`Skipped (not a PDF or image, or over 5 MB): ${skipped.join(', ')}`, `已跳过（不是 PDF 或图片，或超过 5 MB）：${skipped.join('、')}`))
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
      if (input.current) input.current.value = ''
      if (first) onSent(first.ids, first.pair, first.label)
    }
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setOver(false)
        void send(Array.from(e.dataTransfer.files))
      }}
      className={`flex min-h-[8.5rem] flex-col items-center justify-center rounded-box border-[1.5px] border-dashed px-4 py-5 text-center ${over ? 'border-ink bg-sheet' : 'border-rule2 bg-field'}`}
    >
      <input ref={input} type="file" multiple accept=".pdf,.png,.jpg,.jpeg" className="sr-only" onChange={(e) => void send(Array.from(e.target.files ?? []))} />
      <p className="cond text-xl font-bold">{busy ?? tr('Drop invoices here', '把发票拖到这里')}</p>
      <p className="mt-1 text-sm text-ink2">
        {tr('PDF, PNG or JPG, several at a time. They go to ', 'PDF、PNG 或 JPG，可以一次拖多张，会发给')}
        <strong>{targetName(target, tr)}</strong>
        {tr('.', '。')}
      </p>
      <button type="button" className="btn btn-line mt-3 py-1.5" onClick={() => input.current?.click()} disabled={!!busy}>
        {tr('Choose files', '选择文件')}
      </button>
      {err && <p role="alert" className="mt-2 text-sm font-semibold text-cinnabar">{err}</p>}
    </div>
  )
}

/** The same invoice through both agents, next to each other. This is the stage moment. */
function Compare({ pair, attempts, symbol, onOpen, onClose }: { pair: Pair; attempts: Attempt[]; symbol: string; onOpen: (id: string) => void; onClose: () => void }) {
  const { tr } = useLang()
  const g = attempts.find((a) => a.id === pair.guarded)
  const n = attempts.find((a) => a.id === pair.naive)
  return (
    <section className="mt-6 ruled-strong bg-field" aria-label={tr('Both agents', '两个 Agent')}>
      <div className="flex items-baseline justify-between gap-3 border-b-[1.5px] border-rule2 px-4 py-3">
        <h2 className="cond min-w-0 truncate text-2xl font-bold">{pair.label}</h2>
        <button type="button" onClick={onClose} className="shrink-0 rounded-box px-2 py-1 text-ink2 hover:bg-paper2" aria-label={tr('Close', '关闭')}>
          ✕
        </button>
      </div>
      <div className="grid md:grid-cols-2">
        <CompareSide agent="guarded" attempt={g} symbol={symbol} onOpen={onOpen} />
        <div className="border-t border-rule md:border-l md:border-t-0">
          <CompareSide agent="naive" attempt={n} symbol={symbol} onOpen={onOpen} />
        </div>
      </div>
    </section>
  )
}

function CompareSide({ agent, attempt: a, symbol, onOpen }: { agent: AgentKind; attempt?: Attempt; symbol: string; onOpen: (id: string) => void }) {
  const { t, tr, lang } = useLang()
  const done = !!a && isDone(a)
  const kind = done ? attemptMark(a!) : null
  const p = a?.proposal
  const mismatch = !!p?.pay_to && !!p?.registry_payout && p.pay_to.toLowerCase() !== p.registry_payout.toLowerCase()
  const top = a?.flags.find((f) => f.severity === 'high') ?? a?.flags[0]
  return (
    <div className="p-4">
      <p className="cond text-xl font-bold">{agent === 'guarded' ? t.agent_guarded : t.agent_naive}</p>
      <p className="mb-3 text-sm text-ink2">{agent === 'guarded' ? t.agent_guarded_hint : t.agent_naive_hint}</p>
      {a ? <StepRow steps={a.steps} /> : <div className="h-24 animate-pulse rounded-box bg-paper2" />}
      {done && a && kind && (
        <div className="mt-4 grid grid-cols-[auto_1fr] items-center gap-4">
          {kind === 'paid' || kind === 'blocked' || kind === 'refused' || kind === 'no_invoice' || kind === 'error' ? <Seal kind={kind} size={104} /> : null}
          <div className="min-w-0">
            <p className="cond text-[1.7rem] font-extrabold leading-tight" style={{ color: kind === 'paid' ? 'var(--jade)' : kind === 'blocked' ? 'var(--cinnabar)' : 'var(--ink)' }}>
              {outcomeLabel(a, t)}
            </p>
            {outcomeReason(a, lang) && <p className="font-semibold">{outcomeReason(a, lang)}</p>}
            {a.outcome === 'refused' && top && <p className="text-sm leading-snug text-ink2">{lang === 'zh' ? top.detail_zh : top.detail_en}</p>}
            {p?.pay_to && (
              <p className="mt-1 text-sm">
                {tr('Asked to pay ', '要求付到 ')}
                <Address value={p.pay_to} className={mismatch || !p.registry_payout ? 'text-cinnabar' : 'text-jade'} />
                {mismatch && <span className="text-ink2">{tr(', registered is ', '，登记的是 ')}<Address value={p.registry_payout} /></span>}
              </p>
            )}
            <p className="mt-2 flex flex-wrap gap-x-4 text-sm">
              {a.tx && <TxLink href={a.tx.explorer_url} hash={a.tx.hash} label={t.view_tx} />}
              <button type="button" className="underline decoration-rule underline-offset-4 hover:decoration-ink" onClick={() => onOpen(a.id)}>
                {tr('Details', '详情')}
              </button>
            </p>
          </div>
        </div>
      )}
      {a && <div className="mt-4"><Decision attempt={a} symbol={symbol} /></div>}
    </div>
  )
}

function BatchBox({ batchId, onStart }: { batchId: string | null; onStart: () => Promise<void> }) {
  const { tr } = useLang()
  const [starting, setStarting] = useState(false)
  const b = useQuery({
    queryKey: ['batch', batchId],
    queryFn: () => api.batch(batchId!),
    enabled: !!batchId,
    refetchInterval: (q) => {
      const d = q.state.data as BatchSummary | undefined
      return d && d.done >= d.total ? false : 1000
    },
  })
  const d = b.data
  const running = !!d && d.done < d.total
  return (
    <section className="ruled bg-field p-4">
      <h2 className="cond text-xl font-bold">{tr('Clean batch', '正常批次')}</h2>
      <p className="mt-0.5 text-sm leading-snug text-ink2">{tr('Every clean test invoice goes through the guarded agent. All of them should get paid.', '把正常的测试发票都交给带防护的 Agent，应该每张都付款。')}</p>
      <button
        type="button"
        className="btn btn-ink mt-3 w-full py-2"
        disabled={starting || running}
        onClick={async () => {
          setStarting(true)
          try {
            await onStart()
          } finally {
            setStarting(false)
          }
        }}
      >
        {running ? tr('Running…', '运行中…') : tr('Run clean batch', '运行正常批次')}
      </button>
      {d && (
        <div className="mt-3">
          <div className="h-1.5 overflow-hidden rounded-full bg-paper2" aria-hidden>
            <div className="h-full bg-jade transition-[width] duration-300" style={{ width: `${(d.done / Math.max(1, d.total)) * 100}%` }} />
          </div>
          <p className="num mt-1.5 text-sm">
            <strong>
              {d.done}/{d.total}
            </strong>{' '}
            {tr('done', '完成')}: <span className="text-jade">{tr(`${d.paid} paid`, `${d.paid} 已支付`)}</span>, {tr(`${d.refused} refused`, `${d.refused} 被拒`)}, {tr(`${d.blocked} blocked`, `${d.blocked} 被拦截`)}
            {d.false_alarms > 0 && <span className="font-semibold text-cinnabar">, {tr(`${d.false_alarms} false alarms`, `${d.false_alarms} 次误报`)}</span>}
          </p>
        </div>
      )}
    </section>
  )
}

function AttemptsTable({ attempts, loading, selected, onSelect, symbol, compact }: { attempts: Attempt[]; loading: boolean; selected: string | null; onSelect: (id: string) => void; symbol: string; compact: boolean }) {
  const { t, tr, lang } = useLang()
  if (loading) return <div className="h-64 animate-pulse rounded-box bg-paper2" aria-hidden />
  if (attempts.length === 0) return <p className="py-8 text-ink2">{tr('Nothing yet. Drop an invoice above.', '还没有记录。把发票拖到上面。')}</p>
  const src = (s: Source) => ({ team: tr('Team', '团队'), batch: tr('Batch', '批次'), bounty: tr('Bounty', '挑战'), seed: tr('Seed', '样本') })[s]
  return (
    <div className="min-w-0 self-start overflow-x-auto ruled bg-field">
      <table className={`w-full border-collapse text-left text-[0.93rem] ${compact ? 'min-w-[34rem]' : 'min-w-[44rem]'}`}>
        <thead>
          <tr className="rule-b bg-paper text-[0.84rem] text-rule2">
            <th className="px-3 py-2 font-normal">{t.col_time}</th>
            {!compact && <th className="px-3 py-2 font-normal">{tr('Source', '来源')}</th>}
            {!compact && <th className="px-3 py-2 font-normal">{t.col_agent}</th>}
            <th className="px-3 py-2 font-normal">{tr('File', '文件')}</th>
            <th className="px-3 py-2 font-normal">{t.col_event}</th>
            <th className="px-3 py-2 font-normal">{t.col_reason}</th>
            <th className="px-3 py-2 text-right font-normal">{t.col_amount}</th>
          </tr>
        </thead>
        <tbody>
          {attempts.map((a) => {
            const mark = attemptMark(a)
            const color = mark === 'paid' ? 'var(--jade)' : mark === 'blocked' ? 'var(--cinnabar)' : 'var(--ink)'
            const active = a.id === selected
            return (
              <tr
                key={a.id}
                onClick={() => onSelect(a.id)}
                onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelect(a.id)}
                tabIndex={0}
                aria-selected={active}
                className={`rule-b cursor-pointer last:border-b-0 ${active ? 'bg-sheet shadow-[inset_3px_0_0_var(--ink)]' : 'hover:bg-sheet'}`}
              >
                <td className="num px-3 py-2 font-mono text-[0.83rem] text-ink2">{clock(a.created_at)}</td>
                {!compact && <td className="px-3 py-2 text-ink2">{src(a.source)}</td>}
                {!compact && <td className="px-3 py-2">{a.agent === 'guarded' ? tr('Guarded', '带防护') : tr('Naive', '裸奔')}</td>}
                <td className="max-w-[12rem] truncate px-3 py-2 font-mono text-[0.83rem]" title={a.file_name ?? ''}>
                  {a.file_name ?? <span className="font-sans text-ink2">{tr('message', '文字')}</span>}
                </td>
                <td className="px-3 py-1.5">
                  <span className="flex items-center gap-2">
                    <SealMark kind={mark} size={26} />
                    <span className="whitespace-nowrap font-semibold" style={{ color }}>
                      {isDone(a) ? outcomeLabel(a, t) : <span className="step-live font-normal text-ink2">{tr('working', '处理中')}</span>}
                    </span>
                  </span>
                </td>
                <td className="px-3 py-2">{outcomeReason(a, lang) || <span className="text-ink2">—</span>}</td>
                <td className="num whitespace-nowrap px-3 py-2 text-right font-mono">
                  {a.proposal?.amount ? (
                    <>
                      {fmtAmount(a.proposal.amount)} <span className="text-[0.78rem] text-ink2">{symbol}</span>
                    </>
                  ) : (
                    <span className="text-ink2">—</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function Drawer({ attempt, symbol, onClose }: { attempt: Attempt; symbol: string; onClose: () => void }) {
  const { t, tr, lang } = useLang()
  const [showHidden, setShowHidden] = useState(true)
  const a = attempt
  const x = a.extraction
  const p = a.proposal
  const ms = stepMs(a)
  const hiddenCount = a.hidden_text?.spans.length ?? 0
  const mismatch = !!p?.pay_to && !!p?.registry_payout && p.pay_to.toLowerCase() !== p.registry_payout.toLowerCase()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const stepName = (n: string) => ({ extract: t.step_extract, hidden_text: t.step_hidden_text, match: t.step_match, guard: t.step_guard, chain: t.step_chain })[n] ?? n
  const mark = attemptMark(a)

  return (
    <aside
      className="fixed inset-0 z-30 overflow-y-auto bg-paper p-2 lg:sticky lg:inset-auto lg:top-4 lg:z-auto lg:max-h-[calc(100dvh-2rem)] lg:self-start lg:bg-transparent lg:p-0"
      aria-label={tr('Attempt detail', '详情')}
    >
      <div className="ruled-strong bg-field">
        <div className="flex items-start justify-between gap-3 border-b-[1.5px] border-rule2 px-4 py-3">
          <div className="min-w-0">
            <p className="truncate font-mono text-sm" title={a.file_name ?? ''}>
              {a.file_name ?? tr('Typed message', '文字消息')}
            </p>
            <p className="text-xs text-ink2">
              {clock(a.created_at)}, {a.agent === 'guarded' ? t.agent_guarded : t.agent_naive}
              {a.latency_ms ? `, ${secs(a.latency_ms)}` : ''}
              {a.nickname && a.source === 'bounty' ? `, ${a.nickname}` : ''}
            </p>
          </div>
          <button type="button" onClick={onClose} className="rounded-box px-2 py-1 text-ink2 hover:bg-paper2" aria-label={tr('Close', '关闭')}>
            ✕
          </button>
        </div>

        <div className="space-y-5 p-4">
          <StepRow steps={a.steps} />
          <p className="num -mt-3 text-xs text-ink2">
            {a.steps
              .filter((s) => ms[s.name] != null)
              .map((s) => `${stepName(s.name)} ${secs(ms[s.name])}`)
              .join(lang === 'zh' ? '，' : ', ')}
          </p>

          {isDone(a) && (
            <div className="flex items-center gap-3">
              <SealMark kind={mark} size={40} />
              <div>
                <p className="cond text-2xl font-bold leading-tight" style={{ color: mark === 'paid' ? 'var(--jade)' : mark === 'blocked' ? 'var(--cinnabar)' : 'var(--ink)' }}>
                  {outcomeLabel(a, t)}
                </p>
                {outcomeReason(a, lang) && <p className="text-[0.95rem]">{outcomeReason(a, lang)}</p>}
              </div>
              {a.tx && (
                <span className="ml-auto text-sm">
                  <TxLink href={a.tx.explorer_url} hash={a.tx.hash} label={t.view_tx} />
                </span>
              )}
            </div>
          )}

          <Decision attempt={a} symbol={symbol} />

          <Section
            title={tr('The file', '原件')}
            right={
              hiddenCount > 0 ? (
                <label className="flex cursor-pointer items-center gap-1.5 text-sm">
                  <input type="checkbox" checked={showHidden} onChange={(e) => setShowHidden(e.target.checked)} className="accent-[var(--cinnabar)]" />
                  {tr('Show hidden text', '显示隐藏文字')}
                </label>
              ) : null
            }
          >
            <InvoicePreview attempt={a} showHidden={showHidden} />
          </Section>

          {a.hidden_text && (
            <Section title={tr('Hidden text', '隐藏文字')}>
              {hiddenCount === 0 ? (
                <p className="text-sm text-ink2">{tr('None. Everything in the file is visible.', '没有，文件里的字都看得见。')}</p>
              ) : (
                <ul className="space-y-2">
                  {a.hidden_text.spans.map((s, i) => (
                    <li key={i} className="border-l-2 border-cinnabar pl-2.5 text-sm">
                      <span className="text-xs text-ink2">
                        {
                          {
                            near_white: tr('near-white text', '接近白色的文字'),
                            tiny_font: tr('tiny font', '极小字号'),
                            off_page: tr('outside the page', '在页面外'),
                            zero_area: tr('zero-size box', '零面积文本框'),
                          }[s.reason]
                        }
                        , {tr('page', '第')} {s.page}
                        {lang === 'zh' ? ' 页' : ''}
                      </span>
                      <span className="block break-words font-mono text-[0.83rem]">{s.text}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          )}

          {x && x.is_invoice && (
            <Section title={tr('Read from the invoice', '识别出的字段')}>
              <dl className="grid grid-cols-[8rem_1fr] overflow-hidden ruled text-sm">
                <Field k={tr('Vendor', '销售方')} v={x.vendor_name} />
                <Field k={tr('Invoice no.', '发票号码')} v={x.invoice_number} mono />
                <Field k={tr('Date / due', '开票 / 到期')} v={[x.invoice_date, x.due_date].filter(Boolean).join(' / ') || null} />
                <Field k={tr('Amount', '金额')} v={x.amount_total != null ? `${fmtAmount(x.amount_total)} ${x.currency ?? ''}` : null} mono />
                <Field k={tr('PO', '采购单')} v={x.po_reference} mono />
                <Field k={tr('Pay to (printed)', '收款地址（发票上）')} v={x.payee_address} mono />
                <Field k={tr('Notes', '备注')} v={x.notes_to_payer} last />
              </dl>
            </Section>
          )}

          {a.flags.length > 0 && (
            <Section title={t.flags_title}>
              <ul className="space-y-1.5">
                {a.flags.map((f) => (
                  <li key={f.code} className="flex gap-2 text-sm leading-snug">
                    <span className="mt-[0.4rem] h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: f.severity === 'high' ? 'var(--cinnabar)' : 'var(--ink-2)' }} aria-hidden />
                    <span>
                      <strong>{flagLabel(f.code, lang)}.</strong> {lang === 'zh' ? f.detail_zh : f.detail_en}
                    </span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {p && (
            <Section title={tr('Proposed payment', '提出的付款')}>
              <div className="grid grid-cols-2 overflow-hidden ruled text-sm">
                <div className="border-r border-rule p-3">
                  <p className="text-xs text-rule2">{tr('Agent asked to pay', 'Agent 要求付到')}</p>
                  <p className={`mt-1 break-all font-mono text-[0.8rem] ${mismatch ? 'font-semibold text-cinnabar' : ''}`}>{p.pay_to ?? '—'}</p>
                </div>
                <div className="p-3">
                  <p className="text-xs text-rule2">{tr('Registry payout', '登记的收款地址')}</p>
                  <p className={`mt-1 break-all font-mono text-[0.8rem] ${p.registry_payout && !mismatch ? 'text-jade' : ''}`}>{p.registry_payout ?? tr('no such vendor', '没有这个供应商')}</p>
                </div>
                <p className={`col-span-2 border-t border-rule px-3 py-2 text-[0.85rem] ${mismatch || !p.registry_payout ? 'text-cinnabar' : 'text-jade'}`}>
                  {!p.registry_payout
                    ? tr("This vendor isn't registered, so the vault won't pay it.", '这个供应商没有登记，金库不会付。')
                    : mismatch
                      ? tr('Different addresses. The vault only pays the registered one.', '地址不一样，金库只会付到登记的那个。')
                      : tr('Same address.', '地址一致。')}
                </p>
              </div>
              <dl className="mt-2 grid grid-cols-[8rem_1fr] overflow-hidden ruled text-sm">
                <Field k={tr('Vendor', '供应商')} v={p.vendor_id ? `#${p.vendor_id} ${p.vendor_name ?? ''}` : p.vendor_name} />
                <Field k={tr('Budget', '预算')} v={p.po_ref ?? (p.po_id ? `#${p.po_id}` : null)} mono />
                <Field k={tr('Amount', '金额')} v={p.amount ? `${fmtAmount(p.amount)} ${symbol}` : null} mono />
                <Field k={tr('Invoice hash', '发票哈希')} v={p.invoice_hash} mono last />
              </dl>
            </Section>
          )}

          <p className="font-mono text-xs text-ink2">id {a.id}</p>
        </div>
      </div>
    </aside>
  )
}

function Section({ title, right, children }: { title: string; right?: ReactNode; children: ReactNode }) {
  return (
    <section>
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <h3 className="cond text-lg font-bold">{title}</h3>
        {right}
      </div>
      {children}
    </section>
  )
}

function Field({ k, v, mono, last }: { k: string; v: string | null | undefined; mono?: boolean; last?: boolean }) {
  return (
    <>
      <dt className={`border-r border-rule bg-paper px-2.5 py-1.5 text-rule2 ${last ? '' : 'border-b'}`}>{k}</dt>
      <dd className={`min-w-0 break-words px-2.5 py-1.5 ${mono ? 'font-mono text-[0.82rem]' : ''} ${last ? '' : 'border-b border-rule'}`}>{v || <span className="text-ink2">—</span>}</dd>
    </>
  )
}
