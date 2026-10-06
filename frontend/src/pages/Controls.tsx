import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { WagmiProvider, useAccount, useConnect, useDisconnect, useSwitchChain, useWriteContract } from 'wagmi'
import { waitForTransactionReceipt } from 'wagmi/actions'
import { parseUnits, type Abi, type Address as Addr, type Hex } from 'viem'
import { api } from '../api/client'
import type { AppConfig, ChangeKind, PendingChange, Registry } from '../api/types'
import { useLang } from '../i18n'
import { Header } from '../components/Header'
import { AdminGate, Address, Countdown, TxLink } from '../components/bits'
import { countersignAbi } from '../abi/Countersign'
import { wagmiConfig } from '../lib/wagmi'
import { CHANGE_LABEL, changeAddress, describeChange } from '../lib/changes'
import { fmtAmount, isAddress, shortAddr } from '../lib/format'

// ---------- owner actions, the same shape for the wallet and the mock ----------
type Action =
  | { type: 'pause' }
  | { type: 'deactivateVendor'; vendorId: number }
  | { type: 'closePO'; poId: number }
  | { type: 'revokeAgent'; agent: string }
  | { type: 'lowerDailyCap'; cap: string }
  | { type: 'execute'; id: string }
  | { type: 'cancel'; id: string }
  | { type: 'queue'; kind: ChangeKind; decoded: Record<string, string | number> }

type Act = (a: Action, onSent?: (hash: string) => void) => Promise<string | void>

interface Signer {
  act: Act
  canSend: boolean // a wallet on the right chain, or the mock
  isOwner: boolean
}

async function mockAct(a: Action): Promise<void> {
  const o = api.mockOwner!
  switch (a.type) {
    case 'pause':
      return o.pause()
    case 'deactivateVendor':
      return o.deactivateVendor(a.vendorId)
    case 'closePO':
      return o.closePO(a.poId)
    case 'revokeAgent':
      return o.revokeAgent(a.agent)
    case 'lowerDailyCap':
      return o.lowerDailyCap(a.cap)
    case 'execute':
      return o.execute(a.id)
    case 'cancel':
      return o.cancel(a.id)
    case 'queue':
      return o.queue(a.kind, a.decoded)
  }
}

/** Expiry dates are typed as calendar days in China time and stored as the end of that day. */
const endOfDayCST = (date: string) => BigInt(Math.floor(new Date(`${date}T23:59:59+08:00`).getTime() / 1000))

function toCall(a: Action, decimals: number): { functionName: string; args: readonly unknown[] } {
  const u = (v: string | number) => parseUnits(String(v), decimals)
  switch (a.type) {
    case 'pause':
      return { functionName: 'pause', args: [] }
    case 'deactivateVendor':
      return { functionName: 'deactivateVendor', args: [BigInt(a.vendorId)] }
    case 'closePO':
      return { functionName: 'closePO', args: [BigInt(a.poId)] }
    case 'revokeAgent':
      return { functionName: 'revokeAgent', args: [a.agent as Addr] }
    case 'lowerDailyCap':
      return { functionName: 'lowerDailyCap', args: [u(a.cap)] }
    case 'execute':
      return { functionName: 'execute', args: [a.id as Hex] }
    case 'cancel':
      return { functionName: 'cancel', args: [a.id as Hex] }
    case 'queue': {
      const d = a.decoded
      switch (a.kind) {
        case 'AddVendor':
          return { functionName: 'queueAddVendor', args: [BigInt(d.vendor_id), d.payout as Addr] }
        case 'SetPayout':
          return { functionName: 'queueSetPayout', args: [BigInt(d.vendor_id), d.new_payout as Addr] }
        case 'AddPO':
          return { functionName: 'queueAddPO', args: [BigInt(d.po_id), BigInt(d.vendor_id), u(d.cap), endOfDayCST(String(d.expiry)), Number(d.period_days ?? 0)] }
        case 'AddAgent':
          return { functionName: 'queueAddAgent', args: [d.agent as Addr] }
        case 'RaiseDailyCap':
          return { functionName: 'queueRaiseDailyCap', args: [u(d.new_cap)] }
        case 'Unpause':
          return { functionName: 'queueUnpause', args: [] }
        case 'Withdraw':
          return { functionName: 'queueWithdraw', args: [u(d.amount)] }
      }
    }
  }
}

// ---------- page ----------
export default function ControlsPage() {
  const config = useQuery({ queryKey: ['config'], queryFn: api.config, staleTime: 60_000 })
  return (
    <div className="min-h-dvh">
      <Header />
      <AdminGate>
        {!config.data ? (
          <div className="mx-auto mt-10 h-40 max-w-6xl animate-pulse rounded-box bg-paper2" />
        ) : api.mode === 'mock' ? (
          <Controls config={config.data} signer={{ act: mockAct, canSend: true, isOwner: true }} banner={<MockBanner />} />
        ) : (
          <WagmiProvider config={wagmiConfig}>
            <LiveControls config={config.data} />
          </WagmiProvider>
        )}
      </AdminGate>
    </div>
  )
}

function MockBanner() {
  const { tr } = useLang()
  return (
    <p className="rounded-box border border-dashed border-ink2 px-3 py-2 text-sm text-ink2">
      {tr('Mock mode. No wallet needed and nothing goes on-chain.', '演示模式：不用连钱包，也不会上链。')}
    </p>
  )
}

function LiveControls({ config }: { config: AppConfig }) {
  const { tr } = useLang()
  const account = useAccount()
  const { connectors, connect, isPending: connecting, error: connectError } = useConnect()
  const { disconnect } = useDisconnect()
  const { switchChain, isPending: switching } = useSwitchChain()
  const { writeContractAsync } = useWriteContract()

  const rightChain = account.chainId === config.chain_id
  const isOwner = !!account.address && account.address.toLowerCase() === config.owner_address.toLowerCase()
  const chainId = config.chain_id as 677 | 968

  const act: Act = useCallback(
    async (a, onSent) => {
      const call = toCall(a, config.token.decimals)
      // BOT Chain has no EIP-1559, so the wallet must send a legacy (gasPrice) transaction
      const hash = await writeContractAsync({
        address: config.contract_address as Addr,
        abi: countersignAbi as Abi,
        functionName: call.functionName,
        args: call.args,
        chainId,
        type: 'legacy',
      } as never)
      onSent?.(hash)
      const receipt = await waitForTransactionReceipt(wagmiConfig, { hash, chainId })
      if (receipt.status !== 'success') throw new Error(tr('The transaction reverted.', '交易被回滚了。'))
      // the public RPC has no eth_getLogs, so tell the backend which tx to index
      await api.ownerTx(hash).catch(() => undefined)
      return hash
    },
    [config, chainId, writeContractAsync, tr],
  )

  const banner = (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3 ruled bg-field px-3 py-2.5">
        {account.isConnected ? (
          <>
            <span className="text-sm text-ink2">{tr('Wallet', '钱包')}</span>
            <Address value={account.address} lead={8} tail={6} />
            <span className="text-sm text-ink2">{account.chain?.name ?? `chain ${account.chainId}`}</span>
            <button type="button" className="ml-auto text-sm text-ink2 underline underline-offset-4" onClick={() => disconnect()}>
              {tr('Disconnect', '断开')}
            </button>
          </>
        ) : (
          <>
            <span className="text-[0.95rem]">{tr('Connect the owner wallet.', '连接所有者钱包。')}</span>
            <span className="ml-auto flex flex-wrap gap-2">
              {connectors.length === 0 && <span className="text-sm text-cinnabar">{tr('No browser wallet found. Install MetaMask or OKX Wallet.', '没有找到浏览器钱包，请安装 MetaMask 或 OKX Wallet。')}</span>}
              {connectors.map((c) => (
                <button key={c.uid} type="button" className="btn btn-ink py-1.5" disabled={connecting} onClick={() => connect({ connector: c, chainId })}>
                  {c.name === 'Injected' ? tr('Browser wallet', '浏览器钱包') : c.name}
                </button>
              ))}
            </span>
          </>
        )}
      </div>
      {connectError && <p className="text-sm text-cinnabar">{(connectError as { shortMessage?: string }).shortMessage ?? connectError.message}</p>}
      {account.isConnected && !rightChain && (
        <div className="flex flex-wrap items-center gap-3 border-l-2 border-cinnabar bg-field px-3 py-2">
          <span>{tr(`The wallet is on another network. Switch to ${config.network === 'mainnet' ? 'BOT Chain' : 'BOT Chain Testnet'} (${config.chain_id}).`, `钱包在别的网络上。请切换到 ${config.network === 'mainnet' ? 'BOT Chain' : 'BOT Chain 测试网'}（${config.chain_id}）。`)}</span>
          <button type="button" className="btn btn-line py-1" disabled={switching} onClick={() => switchChain({ chainId })}>
            {tr('Switch network', '切换网络')}
          </button>
        </div>
      )}
      {account.isConnected && !isOwner && (
        <p className="border-l-2 border-cinnabar bg-field px-3 py-2 text-[0.95rem]">
          {tr("This wallet isn't the owner ", '这个钱包不是所有者')}
          {tr('(', '（')}
          <Address value={config.owner_address} />
          {tr('), so the owner buttons are off. You can still execute changes whose timer has run out.', '），所有者按钮已关闭。倒计时结束的变更仍然可以执行。')}
        </p>
      )}
    </div>
  )

  return <Controls config={config} signer={{ act, canSend: account.isConnected && rightChain, isOwner }} banner={banner} />
}

// ---------- the panels ----------
function Controls({ config, signer, banner }: { config: AppConfig; signer: Signer; banner: ReactNode }) {
  const { tr, lang } = useLang()
  const qc = useQueryClient()
  const reg = useQuery({ queryKey: ['registry'], queryFn: api.registry, refetchInterval: 3000 })
  const [busy, setBusy] = useState<string | null>(null)
  const [status, setStatus] = useState<{ tone: 'ok' | 'err' | 'wait'; text: string; hash?: string } | null>(null)
  const symbol = config.token.symbol
  const wait = config.timelock_seconds ?? 120
  const waitText =
    wait >= 3600
      ? tr(`${Math.round(wait / 3600)} h`, `${Math.round(wait / 3600)} 小时`)
      : wait >= 60
        ? tr(`${Math.round(wait / 60)} min`, `${Math.round(wait / 60)} 分钟`)
        : tr(`${wait} s`, `${wait} 秒`)
  const explorerTx = (h: string) => `${config.explorer_url.replace(/\/+$/, '')}/tx/${h}`

  const run = useCallback(
    async (key: string, a: Action, done?: () => void) => {
      setBusy(key)
      setStatus({ tone: 'wait', text: api.mode === 'mock' ? tr('Working…', '处理中…') : tr('Confirm in your wallet…', '请在钱包里确认…') })
      try {
        const hash = await signer.act(a, (h) => setStatus({ tone: 'wait', text: tr('Sent. Waiting for the block…', '已发送，等待出块…'), hash: h }))
        setStatus({ tone: 'ok', text: api.mode === 'mock' ? tr('Done (simulated).', '完成（模拟）。') : tr('Confirmed on-chain.', '已上链确认。'), hash: hash || undefined })
        done?.()
      } catch (e) {
        const m = (e as { shortMessage?: string }).shortMessage ?? (e instanceof Error ? e.message : String(e))
        setStatus({ tone: 'err', text: m })
      } finally {
        setBusy(null)
        void qc.invalidateQueries({ queryKey: ['registry'] })
        void qc.invalidateQueries({ queryKey: ['ledger'] })
      }
    },
    [signer, qc, tr],
  )

  const r = reg.data
  const owner = signer.canSend && signer.isOwner
  const unpausePending = !!r?.pending_changes.some((c) => c.kind === 'Unpause')

  return (
    <main className="mx-auto max-w-6xl px-4 pb-24 pt-6">
      <h1 className="cond text-[2.4rem] font-extrabold leading-tight">{tr('Controls', '控制台')}</h1>
      <p className="max-w-[44rem] text-ink2">
        {tr(
          `Changes that make the vault safer apply at once. Anything that could move money waits ${waitText}, which leaves time to cancel it if the owner key is stolen.`,
          `让金库更安全的操作马上生效。可能让钱流出去的操作要等${waitText}，万一所有者密钥被盗，还来得及取消。`,
        )}
      </p>
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
        <span className="flex items-center gap-1.5">
          <Tag kind="now" /> {tr('applies at once', '马上生效')}
        </span>
        <span className="flex items-center gap-1.5">
          <Tag kind="wait" text={waitText} /> {tr('queued first, then anyone can execute it', '先排队，时间到了谁都能执行')}
        </span>
      </div>

      <div className="mt-5">{banner}</div>

      {!r ? (
        <div className="mt-6 h-64 animate-pulse rounded-box bg-paper2" />
      ) : (
        <div className="mt-6 space-y-6">
          {/* status */}
          <section className="grid overflow-hidden ruled-strong bg-field sm:grid-cols-[repeat(4,minmax(0,1fr))_auto]">
            <Figure label={tr('Payments', '付款')} value={r.paused ? tr('Paused', '已暂停') : tr('Running', '正常')} color={r.paused ? 'var(--cinnabar)' : 'var(--jade)'} />
            <Figure label={tr('In the vault', '金库余额')} value={fmtAmount(r.vault_balance)} unit={symbol} />
            <Figure label={tr('Daily cap', '每日限额')} value={fmtAmount(r.daily_cap)} unit={symbol} />
            <Figure label={tr('Left today', '今日剩余')} value={fmtAmount(r.remaining_today)} unit={symbol} />
            <div className="flex items-center gap-2 border-t border-rule p-4 sm:border-l sm:border-t-0">
              {r.paused ? (
                <button type="button" className="btn btn-line w-full whitespace-nowrap" disabled={!owner || busy !== null || unpausePending} onClick={() => run('unpause', { type: 'queue', kind: 'Unpause', decoded: {} })}>
                  {unpausePending ? tr('Resume queued', '恢复已排队') : tr('Resume payments', '恢复付款')} <Tag kind="wait" text={waitText} />
                </button>
              ) : (
                <button type="button" className="btn btn-cinnabar w-full whitespace-nowrap" disabled={!owner || busy !== null} onClick={() => run('pause', { type: 'pause' })}>
                  {tr('Pause all payments', '暂停所有付款')} <Tag kind="now" />
                </button>
              )}
            </div>
          </section>

          <Pending reg={r} symbol={symbol} canSend={signer.canSend} isOwner={owner} busy={busy} run={run} />

          <Vendors reg={r} owner={owner} busy={busy} run={run} waitText={waitText} />
          <Budgets reg={r} owner={owner} busy={busy} run={run} waitText={waitText} symbol={symbol} />

          <div className="grid gap-6 lg:grid-cols-3">
            <DailyCap reg={r} owner={owner} busy={busy} run={run} waitText={waitText} symbol={symbol} />
            <Agents reg={r} owner={owner} busy={busy} run={run} waitText={waitText} />
            <Withdraw reg={r} owner={owner} busy={busy} run={run} waitText={waitText} symbol={symbol} />
          </div>
        </div>
      )}

      {status && (
        <div role="status" className="fixed inset-x-0 bottom-0 z-40 px-4 pb-4">
          <div
            className={`mx-auto flex max-w-xl items-center gap-3 rounded-box border bg-field px-4 py-3 shadow-[0_2px_0_var(--shadow)] ${status.tone === 'err' ? 'border-cinnabar' : status.tone === 'ok' ? 'border-jade' : 'border-ink'}`}
          >
            <span className={`min-w-0 flex-1 text-[0.95rem] ${status.tone === 'err' ? 'text-cinnabar' : ''}`}>
              {status.text} {status.hash && api.mode === 'live' && <TxLink href={explorerTx(status.hash)} hash={status.hash} />}
            </span>
            {status.tone !== 'wait' && (
              <button type="button" className="text-ink2" onClick={() => setStatus(null)} aria-label={lang === 'zh' ? '关闭' : 'Dismiss'}>
                ✕
              </button>
            )}
          </div>
        </div>
      )}
    </main>
  )
}

type Run = (key: string, a: Action, done?: () => void) => Promise<void>
interface PanelProps {
  reg: Registry
  owner: boolean
  busy: string | null
  run: Run
  waitText: string
}

function Tag({ kind, text }: { kind: 'now' | 'wait'; text?: string }) {
  const { tr } = useLang()
  return kind === 'now' ? (
    <span className="inline-flex items-center rounded-[2px] bg-ink px-1.5 py-px text-[0.72rem] font-semibold leading-tight text-field">{tr('instant', '立即')}</span>
  ) : (
    <span className="inline-flex items-center rounded-[2px] border border-dashed border-cinnabar px-1.5 py-px text-[0.72rem] font-semibold leading-tight text-cinnabar">{tr(`waits ${text}`, `等待 ${text}`)}</span>
  )
}

function Figure({ label, value, unit, color }: { label: string; value: string; unit?: string; color?: string }) {
  return (
    <div className="border-rule p-4 [&:not(:first-child)]:border-t sm:[&:not(:first-child)]:border-l sm:[&:not(:first-child)]:border-t-0">
      <p className="text-sm text-ink2">{label}</p>
      <p className="num cond-x mt-0.5 text-[2.2rem] font-bold leading-none" style={{ color: color ?? 'var(--ink)' }}>
        {value}
        {unit && <span className="ml-1 text-sm font-semibold">{unit}</span>}
      </p>
    </div>
  )
}

function Panel({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="ruled bg-field">
      <div className="rule-b px-4 py-3">
        <h2 className="cond text-xl font-bold leading-tight">{title}</h2>
        {note && <p className="text-sm text-ink2">{note}</p>}
      </div>
      {children}
    </section>
  )
}

function Pending({ reg, symbol, canSend, isOwner, busy, run }: { reg: Registry; symbol: string; canSend: boolean; isOwner: boolean; busy: string | null; run: Run }) {
  const { tr, lang } = useLang()
  const list = [...reg.pending_changes].sort((a, b) => a.eta.localeCompare(b.eta))
  return (
    <Panel title={tr('Waiting changes', '等待中的变更')} note={tr('Anyone can execute once the timer runs out. Only the owner can cancel.', '倒计时结束后谁都能执行，只有所有者能取消。')}>
      {list.length === 0 ? (
        <p className="px-4 py-4 text-ink2">{tr('Nothing waiting.', '没有等待中的变更。')}</p>
      ) : (
        <ul className="divide-y divide-rule">
          {list.map((c) => (
            <PendingRow key={c.id} c={c} reg={reg} symbol={symbol} lang={lang} canSend={canSend} isOwner={isOwner} busy={busy} run={run} />
          ))}
        </ul>
      )}
    </Panel>
  )
}

function PendingRow({ c, reg, symbol, lang, canSend, isOwner, busy, run }: { c: PendingChange; reg: Registry; symbol: string; lang: 'zh' | 'en'; canSend: boolean; isOwner: boolean; busy: string | null; run: Run }) {
  const { tr } = useLang()
  const [ready, setReady] = useState(() => c.ready || Date.parse(c.eta) <= Date.now())
  const onDone = useCallback(() => setReady(true), [])
  const addr = changeAddress(c.kind, c.decoded)
  const known = addr && reg.vendors.some((v) => v.payout.toLowerCase() === addr.toLowerCase())
  return (
    <li className="grid gap-3 px-4 py-3 md:grid-cols-[1fr_auto_auto] md:items-center">
      <div className="min-w-0">
        <p className="font-semibold">
          {CHANGE_LABEL[c.kind][lang]}
          <span className="ml-2 font-normal text-ink2">{describeChange(c.kind, c.decoded, reg, lang, symbol)}</span>
        </p>
        {addr && (
          <p className={`mt-0.5 break-all font-mono text-[0.85rem] ${known ? '' : 'text-cinnabar'}`}>
            {addr}
            {!known && c.kind === 'SetPayout' && <span className="ml-2 font-sans text-xs">{tr('not an address we know', '陌生地址')}</span>}
          </p>
        )}
        <p className="font-mono text-xs text-ink2" title={c.id}>
          {shortAddr(c.id, 10, 6)}
        </p>
      </div>
      <div className="text-right md:min-w-[8rem]">
        {ready ? (
          <span className="cond text-xl font-bold text-jade">{tr('Ready', '可执行')}</span>
        ) : (
          <span className="text-sm text-ink2">
            {tr('ready in', '还剩')} <span className="text-2xl text-ink">{<Countdown to={c.eta} onDone={onDone} />}</span>
          </span>
        )}
      </div>
      <div className="flex gap-2">
        <button type="button" className="btn btn-ink py-1.5" disabled={!ready || !canSend || busy !== null} onClick={() => run(`exec-${c.id}`, { type: 'execute', id: c.id })}>
          {tr('Execute', '执行')}
        </button>
        <button type="button" className="btn btn-cinnabar py-1.5" disabled={!isOwner || busy !== null} onClick={() => run(`cancel-${c.id}`, { type: 'cancel', id: c.id })}>
          {tr('Cancel', '取消')}
        </button>
      </div>
    </li>
  )
}

function Vendors({ reg, owner, busy, run, waitText }: PanelProps) {
  const { tr, lang } = useLang()
  const [editing, setEditing] = useState<number | null>(null)
  const [newPayout, setNewPayout] = useState('')
  const [addId, setAddId] = useState('')
  const [addPayout, setAddPayout] = useState('')
  const nextId = useMemo(() => Math.max(0, ...reg.vendors.map((v) => v.id)) + 1, [reg.vendors])
  return (
    <Panel title={tr('Vendors', '供应商')}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem] border-collapse text-left text-[0.93rem]">
          <thead>
            <tr className="rule-b bg-paper text-[0.84rem] text-rule2">
              <th className="w-12 px-4 py-2 font-normal">#</th>
              <th className="px-3 py-2 font-normal">{tr('Name', '名称')}</th>
              <th className="px-3 py-2 font-normal">{tr('Payout address', '收款地址')}</th>
              <th className="px-3 py-2 font-normal">{tr('State', '状态')}</th>
              <th className="px-4 py-2 text-right font-normal" />
            </tr>
          </thead>
          <tbody>
            {reg.vendors.map((v) => (
              <tr key={v.id} className="rule-b align-top last:border-b-0">
                <td className="num px-4 py-2.5 font-mono text-ink2">{v.id}</td>
                <td className="px-3 py-2.5">{lang === 'zh' ? v.name_zh : v.name_en}</td>
                <td className="px-3 py-2.5">
                  <Address value={v.payout} lead={10} tail={8} />
                  {editing === v.id && (
                    <form
                      className="mt-2 flex gap-2"
                      onSubmit={(e) => {
                        e.preventDefault()
                        if (!isAddress(newPayout)) return
                        void run(`payout-${v.id}`, { type: 'queue', kind: 'SetPayout', decoded: { vendor_id: v.id, new_payout: newPayout.trim() } }, () => {
                          setEditing(null)
                          setNewPayout('')
                        })
                      }}
                    >
                      <input className="field py-1.5 font-mono text-[0.85rem]" placeholder="0x…" value={newPayout} onChange={(e) => setNewPayout(e.target.value)} spellCheck={false} aria-label={tr('New payout address', '新收款地址')} />
                      <button type="submit" className="btn btn-ink whitespace-nowrap py-1.5" disabled={!isAddress(newPayout) || busy !== null}>
                        {tr('Queue', '排队')} <Tag kind="wait" text={waitText} />
                      </button>
                    </form>
                  )}
                </td>
                <td className="px-3 py-2.5">{v.active ? <span className="text-jade">{tr('Active', '启用')}</span> : <span className="text-cinnabar">{tr('Off', '已停用')}</span>}</td>
                <td className="whitespace-nowrap px-4 py-2 text-right">
                  <button type="button" className="mr-2 text-sm underline decoration-rule underline-offset-4 hover:decoration-ink disabled:opacity-50" disabled={!owner} onClick={() => setEditing(editing === v.id ? null : v.id)}>
                    {editing === v.id ? tr('Close', '收起') : tr('Change payout', '改收款地址')}
                  </button>
                  <button type="button" className="btn btn-cinnabar py-1 text-sm" disabled={!owner || !v.active || busy !== null} onClick={() => run(`deact-${v.id}`, { type: 'deactivateVendor', vendorId: v.id })}>
                    {tr('Deactivate', '停用')} <Tag kind="now" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form
        className="flex flex-wrap items-end gap-2 border-t border-rule bg-paper px-4 py-3"
        onSubmit={(e) => {
          e.preventDefault()
          const id = Number(addId || nextId)
          if (!isAddress(addPayout) || !Number.isInteger(id) || id <= 0) return
          void run('add-vendor', { type: 'queue', kind: 'AddVendor', decoded: { vendor_id: id, payout: addPayout.trim() } }, () => {
            setAddId('')
            setAddPayout('')
          })
        }}
      >
        <label className="w-24 text-sm text-ink2">
          {tr('Vendor #', '编号')}
          <input className="field mt-0.5 py-1.5 font-mono" inputMode="numeric" placeholder={String(nextId)} value={addId} onChange={(e) => setAddId(e.target.value.replace(/\D/g, ''))} />
        </label>
        <label className="min-w-[16rem] flex-1 text-sm text-ink2">
          {tr('Payout address', '收款地址')}
          <input className="field mt-0.5 py-1.5 font-mono text-[0.88rem]" placeholder="0x…" spellCheck={false} value={addPayout} onChange={(e) => setAddPayout(e.target.value)} />
        </label>
        <button type="submit" className="btn btn-ink py-2" disabled={!owner || !isAddress(addPayout) || busy !== null}>
          {tr('Add vendor', '新增供应商')} <Tag kind="wait" text={waitText} />
        </button>
      </form>
    </Panel>
  )
}

function Budgets({ reg, owner, busy, run, waitText, symbol }: PanelProps & { symbol: string }) {
  const { tr, lang } = useLang()
  const nextId = useMemo(() => Math.max(0, ...reg.pos.map((p) => p.po_id)) + 1, [reg.pos])
  const [f, setF] = useState({ po_id: '', vendor_id: String(reg.vendors[0]?.id ?? 1), cap: '', expiry: '2026-12-31', period_days: '0' })
  const vname = (id: number) => {
    const v = reg.vendors.find((x) => x.id === id)
    return v ? (lang === 'zh' ? v.name_zh : v.name_en) : `#${id}`
  }
  const valid = Number(f.cap) > 0 && /^\d{4}-\d{2}-\d{2}$/.test(f.expiry)
  return (
    <Panel title={tr('Budgets', '预算')}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[46rem] border-collapse text-left text-[0.93rem]">
          <thead>
            <tr className="rule-b bg-paper text-[0.84rem] text-rule2">
              <th className="px-4 py-2 font-normal">{tr('Budget', '预算')}</th>
              <th className="px-3 py-2 font-normal">{tr('Vendor', '供应商')}</th>
              <th className="px-3 py-2 text-right font-normal">{tr('Cap', '上限')}</th>
              <th className="w-[11rem] px-3 py-2 font-normal">{tr('Left', '剩余')}</th>
              <th className="px-3 py-2 font-normal">{tr('Period', '周期')}</th>
              <th className="px-3 py-2 font-normal">{tr('Expires', '到期')}</th>
              <th className="px-4 py-2 text-right font-normal" />
            </tr>
          </thead>
          <tbody>
            {reg.pos.map((p) => {
              const share = Number(p.cap) > 0 ? Math.max(0, Math.min(1, Number(p.remaining) / Number(p.cap))) : 0
              return (
                <tr key={p.po_id} className={`rule-b last:border-b-0 ${p.closed ? 'text-ink2' : ''}`}>
                  <td className="px-4 py-2.5 font-mono text-[0.88rem]">{p.ref}</td>
                  <td className="px-3 py-2.5">{vname(p.vendor_id)}</td>
                  <td className="num px-3 py-2.5 text-right font-mono">{fmtAmount(p.cap)}</td>
                  <td className="px-3 py-2.5">
                    <span className="num font-mono">{fmtAmount(p.remaining)}</span> <span className="text-xs text-ink2">{symbol}</span>
                    <span className="mt-1 block h-1 overflow-hidden rounded-full bg-paper2" aria-hidden>
                      <span className="block h-full bg-jade" style={{ width: `${share * 100}%` }} />
                    </span>
                  </td>
                  <td className="px-3 py-2.5">{p.period_days > 0 ? tr(`every ${p.period_days} days`, `每 ${p.period_days} 天`) : tr('one-off', '一次性')}</td>
                  <td className="num px-3 py-2.5 font-mono text-[0.88rem]">{p.expiry}</td>
                  <td className="px-4 py-2 text-right">
                    {p.closed ? (
                      <span className="text-sm text-cinnabar">{tr('Closed', '已关闭')}</span>
                    ) : (
                      <button type="button" className="btn btn-cinnabar whitespace-nowrap py-1 text-sm" disabled={!owner || busy !== null} onClick={() => run(`close-${p.po_id}`, { type: 'closePO', poId: p.po_id })}>
                        {tr('Close', '关闭')} <Tag kind="now" />
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <form
        className="grid grid-cols-2 items-end gap-2 border-t border-rule bg-paper px-4 py-3 sm:grid-cols-[5.5rem_1fr_7rem_9.5rem_6rem_auto]"
        onSubmit={(e) => {
          e.preventDefault()
          if (!valid) return
          const po_id = Number(f.po_id || nextId)
          void run('add-po', { type: 'queue', kind: 'AddPO', decoded: { po_id, vendor_id: Number(f.vendor_id), cap: f.cap, expiry: f.expiry, period_days: Number(f.period_days || 0) } }, () => setF({ ...f, po_id: '', cap: '' }))
        }}
      >
        <label className="text-sm text-ink2">
          {tr('Budget #', '编号')}
          <input className="field mt-0.5 py-1.5 font-mono" inputMode="numeric" placeholder={String(nextId)} value={f.po_id} onChange={(e) => setF({ ...f, po_id: e.target.value.replace(/\D/g, '') })} />
        </label>
        <label className="text-sm text-ink2">
          {tr('Vendor', '供应商')}
          <select className="field mt-0.5 py-1.5" value={f.vendor_id} onChange={(e) => setF({ ...f, vendor_id: e.target.value })}>
            {reg.vendors.map((v) => (
              <option key={v.id} value={v.id}>
                #{v.id} {lang === 'zh' ? v.name_zh : v.name_en}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-ink2">
          {tr(`Cap (${symbol})`, `上限（${symbol}）`)}
          <input className="field mt-0.5 py-1.5 font-mono" inputMode="decimal" placeholder="10.00" value={f.cap} onChange={(e) => setF({ ...f, cap: e.target.value.replace(/[^\d.]/g, '') })} />
        </label>
        <label className="text-sm text-ink2">
          {tr('Expires', '到期日')}
          <input className="field mt-0.5 py-1.5 font-mono" type="date" value={f.expiry} onChange={(e) => setF({ ...f, expiry: e.target.value })} />
        </label>
        <label className="text-sm text-ink2">
          {tr('Refill days', '周期天数')}
          <input className="field mt-0.5 py-1.5 font-mono" inputMode="numeric" title={tr('0 means a one-off budget', '0 表示一次性预算')} value={f.period_days} onChange={(e) => setF({ ...f, period_days: e.target.value.replace(/\D/g, '') })} />
        </label>
        <button type="submit" className="btn btn-ink col-span-2 whitespace-nowrap py-2 sm:col-span-1" disabled={!owner || !valid || busy !== null}>
          {tr('Add budget', '新增预算')} <Tag kind="wait" text={waitText} />
        </button>
      </form>
    </Panel>
  )
}

function DailyCap({ reg, owner, busy, run, waitText, symbol }: PanelProps & { symbol: string }) {
  const { tr } = useLang()
  const [v, setV] = useState('')
  const n = Number(v)
  const cap = Number(reg.daily_cap)
  const ok = v !== '' && Number.isFinite(n) && n >= 0
  return (
    <Panel title={tr('Daily cap', '每日限额')}>
      <div className="px-4 py-3">
        <p className="num cond-x text-[2rem] font-bold leading-none">
          {fmtAmount(reg.daily_cap)} <span className="text-sm font-semibold">{symbol}</span>
        </p>
        <p className="text-sm text-ink2">{tr(`${fmtAmount(reg.remaining_today)} left today`, `今日还剩 ${fmtAmount(reg.remaining_today)}`)}</p>
        <input className="field mt-3 py-1.5 font-mono" inputMode="decimal" placeholder={tr('New cap', '新限额')} value={v} onChange={(e) => setV(e.target.value.replace(/[^\d.]/g, ''))} aria-label={tr('New daily cap', '新的每日限额')} />
        <div className="mt-2 grid grid-cols-2 gap-2">
          <button type="button" className="btn btn-line px-2 py-1.5 text-sm" disabled={!owner || !ok || n >= cap || busy !== null} onClick={() => run('lower-cap', { type: 'lowerDailyCap', cap: v }, () => setV(''))}>
            {tr('Lower', '降低')} <Tag kind="now" />
          </button>
          <button type="button" className="btn btn-line px-2 py-1.5 text-sm" disabled={!owner || !ok || n <= cap || busy !== null} onClick={() => run('raise-cap', { type: 'queue', kind: 'RaiseDailyCap', decoded: { new_cap: v } }, () => setV(''))}>
            {tr('Raise', '提高')} <Tag kind="wait" text={waitText} />
          </button>
        </div>
      </div>
    </Panel>
  )
}

function Agents({ reg, owner, busy, run, waitText }: PanelProps) {
  const { tr } = useLang()
  const [a, setA] = useState('')
  const agents = reg.agents ?? []
  return (
    <Panel title={tr('Agent keys', 'Agent 密钥')}>
      <ul className="divide-y divide-rule">
        {agents.length === 0 && <li className="px-4 py-3 text-sm text-ink2">{tr('No agents listed.', '没有 Agent。')}</li>}
        {agents.map((g) => (
          <li key={g.address} className="flex items-center gap-2 px-4 py-2.5">
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-semibold">{g.label === 'guarded' ? tr('Guarded', '带防护') : g.label === 'naive' ? tr('Naive', '裸奔') : String(g.label)}</span>
              <Address value={g.address} lead={8} tail={6} className={g.active ? '' : 'line-through'} />
              {(g.balance != null || g.gas) && (
                <span className="block text-xs text-ink2">
                  {g.balance != null && tr(`${fmtAmount(g.balance)} BOT`, `${fmtAmount(g.balance)} BOT`)}
                  {g.balance != null && g.gas && tr(', ', '，')}
                  {g.gas === 'sponsored' ? <span className="text-jade">{tr('gas paid by the BOT Chain paymaster', '手续费由 BOT Chain paymaster 代付')}</span> : g.gas === 'self' ? tr('pays its own gas', '自付手续费') : null}
                </span>
              )}
            </span>
            {g.active ? (
              <button type="button" className="btn btn-cinnabar px-2 py-1 text-sm" disabled={!owner || busy !== null} onClick={() => run(`revoke-${g.address}`, { type: 'revokeAgent', agent: g.address })}>
                {tr('Revoke', '撤销')} <Tag kind="now" />
              </button>
            ) : (
              <span className="text-sm text-cinnabar">{tr('Revoked', '已撤销')}</span>
            )}
          </li>
        ))}
      </ul>
      <form
        className="flex gap-2 border-t border-rule bg-paper px-4 py-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (isAddress(a)) void run('add-agent', { type: 'queue', kind: 'AddAgent', decoded: { agent: a.trim() } }, () => setA(''))
        }}
      >
        <input className="field py-1.5 font-mono text-[0.85rem]" placeholder="0x…" spellCheck={false} value={a} onChange={(e) => setA(e.target.value)} aria-label={tr('Agent address', 'Agent 地址')} />
        <button type="submit" className="btn btn-ink whitespace-nowrap px-2.5 py-1.5 text-sm" disabled={!owner || !isAddress(a) || busy !== null}>
          {tr('Add', '新增')} <Tag kind="wait" text={waitText} />
        </button>
      </form>
    </Panel>
  )
}

function Withdraw({ reg, owner, busy, run, waitText, symbol }: PanelProps & { symbol: string }) {
  const { tr } = useLang()
  const [v, setV] = useState('')
  const n = Number(v)
  const ok = v !== '' && n > 0 && n <= Number(reg.vault_balance)
  return (
    <Panel title={tr('Withdraw', '提取')} note={tr('Only to the owner address.', '只能提到所有者地址。')}>
      <div className="px-4 py-3">
        <p className="text-sm text-ink2">{tr('In the vault', '金库余额')}</p>
        <p className="num cond-x text-[2rem] font-bold leading-none">
          {fmtAmount(reg.vault_balance)} <span className="text-sm font-semibold">{symbol}</span>
        </p>
        <div className="mt-3 flex gap-2">
          <input className="field py-1.5 font-mono" inputMode="decimal" placeholder={tr('Amount', '金额')} value={v} onChange={(e) => setV(e.target.value.replace(/[^\d.]/g, ''))} aria-label={tr('Amount to withdraw', '提取金额')} />
          <button type="button" className="btn btn-line whitespace-nowrap px-2.5 py-1.5 text-sm" disabled={!owner || !ok || busy !== null} onClick={() => run('withdraw', { type: 'queue', kind: 'Withdraw', decoded: { amount: v } }, () => setV(''))}>
            {tr('Queue', '排队')} <Tag kind="wait" text={waitText} />
          </button>
        </div>
      </div>
    </Panel>
  )
}
