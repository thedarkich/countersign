import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { formatEther, isAddress } from 'viem'
import { api } from '../api/client'
import { useAuth } from '../lib/auth'
import { isRejection, rpcBalance, useDiscoveredWallets, useInjectedWallet, type DiscoveredWallet, type InjectedWallet } from '../lib/injectedWallet'
import { walletApi, WalletApiError, type WalletOverview, type WalletPayee, type WalletPayment } from '../lib/walletApi'
import { browserStore, payOnce, record, type PendingReport } from '../lib/walletSend'
import { useLang } from '../i18n'
import { Header } from '../components/Header'
import { Address } from '../components/bits'
import { clock } from '../lib/format'

type Tr = (en: string, zh: string) => string

export default function WalletPage() {
  const { tr } = useLang()
  const { user, loading } = useAuth()
  let body: ReactNode
  if (api.mode === 'mock') body = <p className="mx-auto mt-16 max-w-md px-4 text-center text-ink2">{tr('The wallet works on the live site only. Mock mode sends nothing.', '钱包只在正式站点可用，演示模式不会发送任何东西。')}</p>
  else if (loading && !user) body = <div className="session-state" role="status">{tr('Checking your session…', '正在检查登录状态…')}</div>
  else if (!user) body = <Navigate to="/login?next=%2Fwallet" replace />
  else body = <Wallet />
  return <div className="workspace"><Header />{body}</div>
}

function explain(e: unknown, tr: Tr, lang: 'zh' | 'en') {
  if (e instanceof WalletApiError) return lang === 'zh' ? e.zh : e.en
  const text = String((e as { shortMessage?: string })?.shortMessage ?? (e as Error)?.message ?? e)
  if (isRejection(e)) return tr('You declined in your wallet. Nothing was sent.', '你在钱包里取消了，没有发送任何东西。')
  if (/insufficient funds/i.test(text)) return tr('Not enough BOT in this wallet for the amount plus gas.', '钱包里的 BOT 不够支付金额和手续费。')
  return text.slice(0, 200)
}

/** Seconds on the server's clock, ticking once a second. */
function useServerNow(data?: WalletOverview, updatedAt = 0) {
  const [, tick] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => tick(n => n + 1), 1000)
    return () => clearInterval(timer)
  }, [])
  const offset = data ? data.now - updatedAt / 1000 : 0
  return Math.floor(Date.now() / 1000 + offset)
}

function Wallet() {
  const { tr, lang } = useLang()
  const qc = useQueryClient()
  const overview = useQuery({ queryKey: ['wallet'], queryFn: walletApi.overview, refetchInterval: 15_000, retry: 1 })
  const now = useServerNow(overview.data, overview.dataUpdatedAt)
  const wallet = useInjectedWallet()
  const refresh = () => qc.invalidateQueries({ queryKey: ['wallet'] })
  const say = (e: unknown) => explain(e, tr, lang)

  if (overview.error) {
    const signedOut = overview.error instanceof WalletApiError && overview.error.status === 401
    return <p role="alert" className="mx-auto mt-16 max-w-md px-4 text-center font-semibold text-cinnabar">{signedOut ? tr('Your session ended. Sign in again.', '登录已失效，请重新登录。') : say(overview.error)}</p>
  }
  const data = overview.data
  return (
    <main tabIndex={-1} className="page-content">
      <h1 className="cond text-[2.4rem] font-extrabold leading-tight">{tr('Wallet', '钱包')}</h1>
      <p className="mt-2 max-w-3xl text-sm text-ink2">{tr('Send BOT from your own wallet, only to addresses you whitelisted and never above your own maximum. Your wallet signs every payment; Countersign never holds your keys or funds.', '用你自己的钱包发送 BOT：只能付到你白名单里的地址，且不超过你设定的单笔上限。每笔付款都由你的钱包签名，Countersign 不会持有你的私钥或资金。')}</p>
      {data && (
        <p className={`mt-3 inline-block rounded-box border px-3 py-1.5 text-sm ${data.network === 'mainnet' ? 'border-cinnabar text-cinnabar' : 'border-rule2 text-ink2'}`}>
          {data.network === 'mainnet' ? tr('BOT Chain mainnet · real BOT', 'BOT Chain 主网 · 真实 BOT') : tr('BOT Chain testnet · test BOT', 'BOT Chain 测试网 · 测试币')} · {tr('chain ID', '链 ID')} {data.chain_id}
        </p>
      )}
      {!data ? <div className="mt-6 h-64 animate-pulse rounded-box bg-paper2" aria-hidden /> : (
        <div className="mt-6 grid gap-5 lg:grid-cols-2">
          <WalletCard data={data} wallet={wallet} onChange={refresh} say={say} />
          <LimitCard data={data} now={now} onChange={refresh} say={say} />
          <PayeesCard data={data} now={now} onChange={refresh} say={say} />
          <SendCard data={data} wallet={wallet} now={now} say={say} />
          <div className="lg:col-span-2"><History explorer={data.explorer_url} /></div>
        </div>
      )}
    </main>
  )
}

function Card({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <section className="ruled bg-field p-4">
      <h2 className="cond text-xl font-bold">{title}</h2>
      {sub && <p className="mt-0.5 text-sm leading-snug text-ink2">{sub}</p>}
      <div className="mt-3">{children}</div>
    </section>
  )
}

function Problem({ text }: { text: string | null }) {
  return text ? <p role="alert" className="mt-2 text-sm font-semibold text-cinnabar">{text}</p> : null
}

function WalletCard({ data, wallet, onChange, say }: { data: WalletOverview; wallet: InjectedWallet; onChange: () => void; say: (e: unknown) => string }) {
  const { tr } = useLang()
  const wallets = useDiscoveredWallets()
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const linked = data.wallet?.address
  const connected = wallet.address
  const balance = useQuery({ queryKey: ['wallet-balance', data.chain_id, linked], queryFn: () => rpcBalance(data.chain_id, linked!), enabled: !!linked, refetchInterval: 15_000, retry: 1 })
  const same = !!linked && !!connected && linked.toLowerCase() === connected.toLowerCase()

  async function run(name: string, task: () => Promise<unknown>) {
    setErr(null)
    setBusy(name)
    try {
      await task()
    } catch (e) {
      setErr(say(e))
    } finally {
      setBusy(null)
    }
  }

  const connect = (candidate: DiscoveredWallet) => run('connect', () => wallet.connect(candidate))

  const link = () => run('link', async () => {
    const address = wallet.address
    if (!address) throw new Error(tr('Your wallet did not share an account. Connect it again.', '钱包没有提供账户，请重新连接。'))
    const { message } = await walletApi.challenge(address)
    const signature = await wallet.sign(message)
    await walletApi.link(address, signature)
    onChange()
  })

  const unlink = () => run('unlink', async () => {
    await walletApi.unlink()
    await wallet.disconnect(true)
    onChange()
  })

  const picker = (
    <div className="flex flex-wrap gap-2">
      {wallets.length === 0 && <p className="text-sm text-ink2">{tr('No browser wallet found. Install MetaMask (or another wallet), then reload this page.', '没有找到浏览器钱包。请安装 MetaMask（或其他钱包）后刷新页面。')}</p>}
      {wallets.map(w => (
        <button key={w.id} type="button" className="btn btn-line flex items-center gap-2 py-1.5" disabled={!!busy} onClick={() => void connect(w)}>
          {w.icon && <img src={w.icon} alt="" className="h-5 w-5" />}
          {busy === 'connect' ? tr('Check your wallet…', '请查看钱包…') : w.name || tr('Browser wallet', '浏览器钱包')}
        </button>
      ))}
    </div>
  )

  return (
    <Card title={tr('1 · Your wallet', '1 · 你的钱包')} sub={tr('Connect the wallet you want to pay from, then link it to your account with a free signature.', '连接你要付款的钱包，再用一次免费签名把它链接到你的账户。')}>
      {linked ? (
        <div className="space-y-2 text-sm">
          <p>{tr('Linked wallet', '已链接钱包')}: <span className="break-all font-mono text-[0.85rem]">{linked}</span></p>
          <p>{tr('Balance', '余额')}: <strong className="num">{balance.data !== undefined ? `${Number(formatEther(balance.data)).toLocaleString(undefined, { maximumFractionDigits: 6 })} BOT` : '—'}</strong></p>
          {!connected && <><p className="text-ink2">{tr('Connect it to send:', '连接它才能付款：')}</p>{picker}</>}
          {connected && !same && (
            <div className="rounded-box border border-cinnabar p-2.5">
              <p className="font-semibold text-cinnabar">{tr('Your wallet is on a different account', '钱包当前是另一个账户')}: <span className="break-all font-mono">{connected}</span></p>
              <p className="mt-1 text-ink2">{tr('Switch to the linked account in your wallet, or link this one instead.', '请在钱包里切换到已链接的账户，或改为链接这个账户。')}</p>
              <button type="button" className="btn btn-line mt-2 py-1.5" disabled={!!busy} onClick={() => void link()}>{busy === 'link' ? tr('Sign in your wallet…', '请在钱包里签名…') : tr('Link this account instead', '改为链接这个账户')}</button>
            </div>
          )}
          {same && wallet.chainId !== data.chain_id && (
            <button type="button" className="btn btn-ink py-1.5" disabled={!!busy} onClick={() => void run('switch', () => wallet.ensureChain(data.chain_id))}>{tr('Switch wallet to BOT Chain', '把钱包切换到 BOT Chain')}</button>
          )}
          {same && wallet.chainId === data.chain_id && <p className="font-semibold text-jade">{tr('Connected and ready to pay.', '已连接，可以付款。')}</p>}
          <button type="button" className="text-sm underline decoration-rule underline-offset-4 hover:decoration-ink" disabled={!!busy} onClick={() => void unlink()}>{tr('Unlink this wallet', '取消链接这个钱包')}</button>
        </div>
      ) : connected ? (
        <div className="space-y-2 text-sm">
          <p>{tr('Connected', '已连接')}: <span className="break-all font-mono text-[0.85rem]">{connected}</span></p>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn btn-ink py-1.5" disabled={!!busy} onClick={() => void link()}>{busy === 'link' ? tr('Sign in your wallet…', '请在钱包里签名…') : tr('Link this wallet to my account', '把这个钱包链接到我的账户')}</button>
            <button type="button" className="btn btn-line py-1.5" disabled={!!busy} onClick={() => void run('disconnect', () => wallet.disconnect())}>{tr('Use another wallet', '换一个钱包')}</button>
          </div>
          <p className="text-xs text-ink2">{tr('Signing is free and sends no transaction. It proves this wallet is yours.', '签名免费，不会发送交易，只用来证明这个钱包属于你。')}</p>
        </div>
      ) : picker}
      <Problem text={err} />
    </Card>
  )
}

function LimitCard({ data, now, onChange, say }: { data: WalletOverview; now: number; onChange: () => void; say: (e: unknown) => string }) {
  const { tr } = useLang()
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const limit = data.limit
  async function save() {
    setErr(null)
    setBusy(true)
    try {
      await walletApi.setLimit(value.trim())
      setValue('')
      onChange()
    } catch (e) {
      setErr(say(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Card title={tr('2 · Your maximum per payment', '2 · 你的单笔上限')} sub={tr(`You choose it. Lowering it takes effect now; raising it waits ${data.payee_delay_seconds} s.`, `由你决定。调低立即生效，调高要等 ${data.payee_delay_seconds} 秒。`)}>
      <p className="text-sm">
        {limit ? <>{tr('Current maximum', '当前上限')}: <strong className="num">{limit.max} BOT</strong></> : <span className="font-semibold text-cinnabar">{tr('Not set yet. Set it before you send.', '还没设置，付款前请先设置。')}</span>}
        {limit?.pending_max && limit.pending_at && <span className="block text-ink2">{tr(`Rising to ${limit.pending_max} BOT in ${Math.max(0, limit.pending_at - now)} s`, `${Math.max(0, limit.pending_at - now)} 秒后提高到 ${limit.pending_max} BOT`)}</span>}
      </p>
      <form className="mt-2 flex gap-2" onSubmit={e => { e.preventDefault(); void save() }}>
        <input className="field num" inputMode="decimal" placeholder="0.05" value={value} onChange={e => setValue(e.target.value)} aria-label={tr('Maximum in BOT', '上限（BOT）')} />
        <button type="submit" className="btn btn-ink shrink-0 py-1.5" disabled={busy || !value.trim()}>{busy ? tr('Saving…', '保存中…') : tr('Save', '保存')}</button>
      </form>
      <Problem text={err} />
    </Card>
  )
}

function PayeesCard({ data, now, onChange, say }: { data: WalletOverview; now: number; onChange: () => void; say: (e: unknown) => string }) {
  const { tr } = useLang()
  const [label, setLabel] = useState('')
  const [address, setAddress] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  async function act(task: () => Promise<unknown>, reset = false) {
    setErr(null)
    setBusy(true)
    try {
      await task()
      if (reset) { setLabel(''); setAddress('') }
      onChange()
    } catch (e) {
      setErr(say(e))
    } finally {
      setBusy(false)
    }
  }
  const valid = isAddress(address.trim(), { strict: false })
  return (
    <Card title={tr('3 · Whitelist', '3 · 白名单')} sub={tr(`Only these addresses can be paid. A new address can receive after ${data.payee_delay_seconds} s.`, `只能付给这些地址。新地址 ${data.payee_delay_seconds} 秒后才能收款。`)}>
      <form className="grid gap-2 sm:grid-cols-[10rem_1fr_auto]" onSubmit={e => { e.preventDefault(); void act(() => walletApi.addPayee(address.trim(), label.trim()), true) }}>
        <input className="field" maxLength={60} placeholder={tr('Name', '名称')} value={label} onChange={e => setLabel(e.target.value)} aria-label={tr('Name', '名称')} />
        <input className="field font-mono text-[0.85rem]" maxLength={42} placeholder="0x…" value={address} onChange={e => setAddress(e.target.value)} aria-label={tr('Address', '地址')} aria-invalid={!!address && !valid} />
        <button type="submit" className="btn btn-ink py-1.5" disabled={busy || !label.trim() || !valid}>{tr('Add', '添加')}</button>
      </form>
      {address && !valid && <p className="mt-1 text-xs text-cinnabar">{tr('Not a valid address yet.', '还不是有效的地址。')}</p>}
      <Problem text={err} />
      {data.payees.length === 0 ? <p className="mt-3 text-sm text-ink2">{tr('No addresses yet.', '还没有地址。')}</p> : (
        <ul className="mt-3 divide-y divide-[var(--rule)] ruled">
          {data.payees.map(p => {
            const wait = p.active_at - now
            return (
              <li key={p.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-sm">
                <span className="font-semibold">{p.label}</span>
                <Address value={p.address} lead={8} tail={6} />
                <span className={`ml-auto text-xs font-semibold ${wait > 0 ? 'text-ink2' : 'text-jade'}`}>{wait > 0 ? tr(`can receive in ${wait} s`, `${wait} 秒后可收款`) : tr('active', '可收款')}</span>
                <button type="button" className="text-xs underline decoration-rule underline-offset-4 hover:decoration-ink" disabled={busy} onClick={() => void act(() => walletApi.removePayee(p.id))}>{tr('Remove', '移除')}</button>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

type Stage = 'approve' | 'switch' | 'sign' | 'report' | null

function SendCard({ data, wallet, now, say }: { data: WalletOverview; wallet: InjectedWallet; now: number; say: (e: unknown) => string }) {
  const { tr } = useLang()
  const qc = useQueryClient()
  const [payeeId, setPayeeId] = useState('')
  const [amount, setAmount] = useState('')
  const [stage, setStage] = useState<Stage>(null)
  const [err, setErr] = useState<string | null>(null)
  const [last, setLast] = useState<WalletPayment | null>(null)
  const store = useMemo(() => browserStore(), [])
  const linked = data.wallet?.address
  const mine = (r: PendingReport) => !!linked && r.wallet.toLowerCase() === linked.toLowerCase()
  // payments the wallet already sent but Countersign has not recorded yet (failed report or a refresh)
  const [unrecorded, setUnrecorded] = useState<PendingReport[]>(() => store.load().filter(mine))
  const [recording, setRecording] = useState(false)
  const ready = !!linked && wallet.address?.toLowerCase() === linked.toLowerCase()
  const selected: WalletPayee | undefined = data.payees.find(p => p.id === payeeId)

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['wallet-payments'] })
    void qc.invalidateQueries({ queryKey: ['wallet-balance'] })
  }

  /** Report the kept hashes again. Never sends: the money already moved. */
  async function recordAll(list = store.load().filter(mine)) {
    setRecording(true)
    try {
      for (const report of list) {
        try {
          setLast(await record(store, report, walletApi.sent))
        } catch (e) {
          setErr(say(e))
        }
      }
    } finally {
      setUnrecorded(store.load().filter(mine))
      setRecording(false)
      refresh()
    }
  }

  // after a refresh, finish reporting anything left from the last visit
  useEffect(() => {
    const left = store.load().filter(mine)
    setUnrecorded(left)
    if (left.length) void recordAll(left)
  }, [linked]) // only when the linked wallet changes

  async function send() {
    setErr(null)
    setLast(null)
    setStage('approve')
    try {
      const result = await payOnce({
        approve: () => walletApi.approve(payeeId, amount.trim()),
        send: async (tx) => {
          if (wallet.chainId !== tx.chain_id) {
            setStage('switch')
            await wallet.ensureChain(tx.chain_id)
          }
          setStage('sign')
          return wallet.send({ to: tx.to, value: tx.value })
        },
        sent: walletApi.sent,
        store,
        onReporting: () => {
          setStage('report')
          setAmount('') // the money moved: never leave the form ready to send it again
        },
      })
      if (result.status === 'recorded') setLast(result.payment)
      else setErr(tr('Your wallet sent this payment, but Countersign could not record it yet. Do not pay again: use “Record it now” below.', '钱包已经发出这笔付款，但 Countersign 还没能记录。请不要重复付款，点击下方的“立即记录”。'))
    } catch (e) {
      setErr(say(e))
    } finally {
      setStage(null)
      setUnrecorded(store.load().filter(mine))
      refresh()
    }
  }

  const label: Record<Exclude<Stage, null>, string> = {
    approve: tr('Countersign is checking your rules…', 'Countersign 正在检查你的规则…'),
    switch: tr('Switch to BOT Chain in your wallet…', '请在钱包里切换到 BOT Chain…'),
    sign: tr('Confirm the payment in your wallet…', '请在钱包里确认付款…'),
    report: tr('Sent. Checking the transaction…', '已发送，正在核对交易…'),
  }
  return (
    <Card title={tr('4 · Send BOT', '4 · 发送 BOT')} sub={tr('Countersign approves the payment against your whitelist and maximum. Then your wallet signs it, and we check what was actually sent.', 'Countersign 先按你的白名单和上限批准，再由你的钱包签名，最后核对实际发出的交易。')}>
      <form className="grid gap-2" onSubmit={e => { e.preventDefault(); void send() }}>
        <select className="field" value={payeeId} onChange={e => setPayeeId(e.target.value)} aria-label={tr('Pay to', '付给')}>
          <option value="">{tr('Choose a whitelisted address…', '选择白名单里的地址…')}</option>
          {data.payees.map(p => (
            <option key={p.id} value={p.id} disabled={p.active_at > now}>
              {p.label} · {p.address.slice(0, 8)}…{p.address.slice(-6)}{p.active_at > now ? ` (${p.active_at - now} s)` : ''}
            </option>
          ))}
        </select>
        <div className="flex gap-2">
          <input className="field num" inputMode="decimal" placeholder={data.limit ? tr(`up to ${data.limit.max}`, `最多 ${data.limit.max}`) : '0.01'} value={amount} onChange={e => setAmount(e.target.value)} aria-label={tr('Amount in BOT', '金额（BOT）')} />
          <span className="self-center text-sm text-ink2">BOT</span>
        </div>
        <button type="submit" className="btn btn-ink py-2" disabled={!!stage || recording || unrecorded.length > 0 || !ready || !selected || !amount.trim()}>
          {stage ? label[stage] : tr('Send with my wallet', '用我的钱包发送')}
        </button>
        {!ready && <p className="text-xs text-ink2">{tr('Connect and link your wallet first (step 1).', '请先连接并链接钱包（第 1 步）。')}</p>}
        {unrecorded.length > 0 && <p className="text-xs text-ink2">{tr('Record the payment below before sending another one.', '请先记录下面这笔付款，再发起新的付款。')}</p>}
      </form>
      <Problem text={err} />
      {unrecorded.map(r => (
        <div key={r.paymentId} role="status" className="mt-3 rounded-box border border-cinnabar p-2.5 text-sm">
          <p className="font-semibold">{tr('Sent from your wallet, not recorded by Countersign yet', '钱包已发出，Countersign 尚未记录')}</p>
          <p className="mt-0.5">
            <strong className="num">{r.amount} BOT</strong> → {r.label} <Address value={r.payee} />
          </p>
          <p className="mt-0.5 text-ink2">{tr('This payment is already on chain. Do not send it again.', '这笔付款已经在链上，请不要再次发送。')}</p>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <button type="button" className="btn btn-ink py-1.5" disabled={recording} onClick={() => void recordAll([r])}>
              {recording ? tr('Recording…', '记录中…') : tr('Record it now', '立即记录')}
            </button>
            <a className="underline decoration-rule underline-offset-4 hover:decoration-ink" href={`${data.explorer_url}/tx/${r.hash}`} target="_blank" rel="noreferrer">{tr('See it on the explorer', '在浏览器中查看')}</a>
          </div>
        </div>
      ))}
      {last && <PaymentLine payment={last} />}
    </Card>
  )
}

function statusText(status: WalletPayment['status'], tr: Tr) {
  return {
    approved: tr('approved', '已批准'),
    sent: tr('waiting for the block', '等待出块'),
    confirmed: tr('confirmed on chain', '链上已确认'),
    failed: tr('failed on chain', '链上失败'),
    mismatch: tr('wallet sent something else', '钱包发送的与批准不符'),
    expired: tr('expired', '已过期'),
  }[status]
}

function PaymentLine({ payment: p }: { payment: WalletPayment }) {
  const { tr } = useLang()
  const color = p.status === 'confirmed' ? 'text-jade' : p.status === 'sent' ? 'text-ink2' : 'text-cinnabar'
  return (
    <div className="mt-3 rounded-box border border-rule p-2.5 text-sm">
      <p>
        <strong className="num">{p.amount} BOT</strong> → {p.payee_label} <Address value={p.payee} />
        <span className={`ml-2 font-semibold ${color}`}>{statusText(p.status, tr)}</span>
      </p>
      {p.detail && <p className="text-cinnabar">{p.detail}</p>}
      {p.explorer_url && <a className="underline decoration-rule underline-offset-4 hover:decoration-ink" href={p.explorer_url} target="_blank" rel="noreferrer">{tr('See the transaction on the explorer', '在浏览器中查看交易')}</a>}
    </div>
  )
}

function History({ explorer }: { explorer: string }) {
  const { tr } = useLang()
  const q = useQuery({
    queryKey: ['wallet-payments'],
    queryFn: walletApi.payments,
    refetchInterval: (query) => (query.state.data?.payments.some(p => p.status === 'sent') ? 4000 : 20_000),
  })
  const rows = q.data?.payments ?? []
  return (
    <Card title={tr('Payments', '付款记录')} sub={tr('Every payment sent through Countersign, checked on chain.', '经 Countersign 发出的每笔付款，都在链上核对过。')}>
      {rows.length === 0 ? <p className="text-sm text-ink2">{tr('No payments yet.', '还没有付款。')}</p> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[36rem] border-collapse text-left text-sm">
            <thead><tr className="rule-b text-[0.84rem] text-rule2"><th className="py-1.5 pr-3 font-normal">{tr('Time', '时间')}</th><th className="py-1.5 pr-3 font-normal">{tr('To', '收款方')}</th><th className="py-1.5 pr-3 text-right font-normal">{tr('Amount', '金额')}</th><th className="py-1.5 pr-3 font-normal">{tr('Status', '状态')}</th><th className="py-1.5 font-normal">{tr('Transaction', '交易')}</th></tr></thead>
            <tbody>
              {rows.map(p => (
                <tr key={p.id} className="rule-b last:border-b-0">
                  <td className="num py-1.5 pr-3 font-mono text-[0.8rem] text-ink2">{clock(p.created_at)}</td>
                  <td className="py-1.5 pr-3">{p.payee_label} <Address value={p.payee} /></td>
                  <td className="num py-1.5 pr-3 text-right font-mono">{p.amount}</td>
                  <td className={`py-1.5 pr-3 font-semibold ${p.status === 'confirmed' ? 'text-jade' : p.status === 'sent' ? 'text-ink2' : 'text-cinnabar'}`}>{statusText(p.status, tr)}{p.detail ? <span className="block text-xs font-normal">{p.detail}</span> : null}</td>
                  <td className="py-1.5">{p.tx_hash ? <a className="font-mono text-[0.8rem] underline decoration-rule underline-offset-4 hover:decoration-ink" href={p.explorer_url ?? `${explorer}/tx/${p.tx_hash}`} target="_blank" rel="noreferrer">{p.tx_hash.slice(0, 10)}…</a> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
