import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useLang } from '../i18n'
import { SiteHeader, SiteFooter } from '../components/SiteChrome'
import { api, getAdminToken } from '../api/client'
import { useAuth } from '../lib/auth'
import '../landing.css'

/** Fades `.reveal` elements in as they scroll into view, then hands them back to their own styles (hover lifts, transitions). */
function useReveal() {
  useEffect(() => {
    const els = Array.from(document.querySelectorAll<HTMLElement>('.reveal'))
    if (!els.length) return
    const timers: number[] = []
    const show = (el: HTMLElement) => {
      el.classList.add('revealed')
      const delay = parseFloat(el.style.getPropertyValue('--reveal-delay')) || 0
      timers.push(window.setTimeout(() => el.classList.remove('reveal', 'revealed'), delay + 800))
    }
    // no observer (older in-app browsers): show everything rather than leave it invisible
    if (!('IntersectionObserver' in window)) {
      els.forEach(show)
      return () => timers.forEach(clearTimeout)
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { show(e.target as HTMLElement); io.unobserve(e.target) }
      })
    }, { threshold: 0.12 })
    els.forEach((el) => io.observe(el))
    return () => { io.disconnect(); timers.forEach(clearTimeout) }
  }, [])
}

/** Pulls a call-to-action a few pixels toward the mouse. Touch input is ignored so a tap never leaves it offset. */
function Magnetic({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  function onMove(e: React.PointerEvent) {
    const el = ref.current
    if (!el || e.pointerType !== 'mouse') return
    const r = el.getBoundingClientRect()
    const x = (e.clientX - r.left - r.width / 2) / (r.width / 2)
    const y = (e.clientY - r.top - r.height / 2) / (r.height / 2)
    el.style.transform = `translate(${x * 5}px, ${y * 5}px)`
  }
  function reset() { const el = ref.current; if (el) el.style.transform = '' }
  return <div ref={ref} className="magnetic" onPointerMove={onMove} onPointerLeave={reset}>{children}</div>
}

const delay = (ms: number) => ({ ['--reveal-delay' as string]: `${ms}ms` })

export default function LandingPage() {
  const { tr } = useLang()
  const config = useQuery({ queryKey: ['config'], queryFn: api.config, staleTime: 60_000 })
  const network = config.data?.network
  const preview = api.mode === 'mock' ? tr('MOCK PREVIEW', '模拟预览') : network === 'testnet' ? tr('BOT TESTNET PREVIEW', 'BOT 测试网预览') : network === 'mainnet' ? tr('BOT MAINNET', 'BOT 主网') : tr('CONNECTING', '正在连接')
  const note = api.mode === 'mock' ? tr('Mock data · Nothing is sent on-chain', '模拟数据 · 不发送链上交易') : network === 'testnet' ? tr('BOT Chain testnet · Test tokens only', 'BOT Chain 测试网 · 仅使用测试代币') : network === 'mainnet' ? tr('BOT Chain mainnet', 'BOT Chain 主网') : ''
  const { user } = useAuth()
  const signedIn = !!user || !!getAdminToken()
  const workspace = signedIn ? '/inbox' : '/login'
  const start = signedIn ? '/inbox' : '/signup'
  const [params] = useSearchParams()
  const [demo, setDemo] = useState<'request' | 'rules' | 'receipt'>('request')
  const [copied, setCopied] = useState(false)
  const sample = JSON.stringify({ vendorId: 7, poId: 101, amount: '100', invoice: 'INV-001' }, null, 2)
  useReveal()
  useEffect(() => {
    document.title = 'Countersign · ' + tr('Your rules. Every payment.', '每笔付款，遵循你的规则。')
    const section = params.get('section')
    if (section === 'workflow' || section === 'stack') document.getElementById(section)?.scrollIntoView({ behavior: 'smooth' })
    else window.scrollTo(0, 0)
  }, [params, tr])
  const steps = [
    ['01', tr('Agent requests', 'Agent 提出付款'), tr('An invoice, a supplier and a purchase order.', '提交发票、供应商和采购单。')],
    ['02', tr('The vault checks', '金库检查规则'), tr('Registered payout. Approved budget. No replay.', '核对收款地址、预算和重复账单。')],
    ['03', tr('Follow the receipt', '查看执行回执'), tr('Paid or blocked. Every decision has a record.', '付款或拒付，每次决定都有记录。')],
  ]
  return <div className="public-site landing-page"><SiteHeader />
    <main className="landing-main" id="main-content" tabIndex={-1}>
      <div className="campaign-strip reveal"><span className="mono-label">◆ {preview}</span><strong>{tr('Let agents work. Keep payments within your rules.', '让 Agent 工作，让付款遵循你的规则。')}</strong><Link to={start} className="site-button">{tr('Get started', '开始使用')} <span aria-hidden>→</span></Link></div>
      <section className="hero-card reveal" style={delay(60)}>
        <div className="hero-copy reveal" style={delay(120)}><p className="mono-label">// {tr('YOUR RULES. EVERY PAYMENT.', '每笔付款，你来定规则。')}</p>
          <h1>{tr('AI checks the invoice.', 'AI 审票。')}<br /><span>{tr('The contract calls the shots.', '合约拍板。')}</span></h1>
          <p>{tr('AI checks invoices. Your contract enforces your payment rules.', 'AI 检查发票，智能合约按你设定的规则放行或拒付。')}</p>
          <div className="hero-actions"><Magnetic><Link to={start} className="site-button">{tr('Open your workspace', '开启工作台')} <span aria-hidden>→</span></Link></Magnetic>{!signedIn && <Link to="/login" className="site-button secondary">{tr('Sign in', '登录')}</Link>}</div>
          {note && <p className="hero-note">{note}</p>}
        </div>
        <div className="hero-demo reveal" style={delay(240)}><p className="mono-label">◆ {tr('ONE REQUEST. CLEAR BOUNDARIES.', '一笔请求，清晰的边界。')}</p>
          <div className="demo-options" role="group" aria-label={tr('Payment demonstration steps', '付款演示步骤')}>
            {(['request', 'rules', 'receipt'] as const).map((v, i) => <button key={v} aria-pressed={demo === v} onClick={() => { setDemo(v); setCopied(false) }}>{['↗', '◇', '✓'][i]} {v === 'request' ? tr('Request', '付款请求') : v === 'rules' ? tr('Rules', '规则检查') : tr('Receipt', '执行回执')}</button>)}
          </div>
          <div className="terminal-card"><div className="terminal-bar"><div className="terminal-lights"><i /><i /><i /></div><span>countersign / {demo}</span><span className="terminal-badge">{tr('EXAMPLE', '演示样例')}</span><button type="button" title={tr('Copy sample request', '复制请求样例')} aria-label={tr('Copy sample request', '复制请求样例')} onClick={async () => { try { await navigator.clipboard.writeText(sample); setCopied(true) } catch { setCopied(false) } }}>{copied ? '✓' : '⧉'}</button></div>
            <div className="terminal-body" aria-live="polite">
              <p className="terminal-comment">{demo === 'request' ? tr('An agent submits a payment request.', 'Agent 提交一笔付款请求。') : demo === 'rules' ? tr('Every check must pass before payment.', '每一项规则都通过，才能付款。') : tr('The receipt explains what happened.', '回执记录发生了什么。')}</p>
              {demo === 'request' ? <pre><span className="terminal-prompt">{'>'} pay </span>{sample}</pre> : demo === 'rules' ? <div className="terminal-checks"><p>✓ {tr('Supplier 7 is active', '供应商 7 已登记且有效')}</p><p>✓ {tr('PO-101 belongs to supplier 7', 'PO-101 归属于供应商 7')}</p><p>✓ {tr('100 is within the approved budget', '100 在批准预算内')}</p><p>✓ {tr('This invoice has not been paid', '这张账单尚未支付')}</p></div> : <div className="terminal-checks"><p>✓ {tr('Paid · 100 example units', '已支付 · 100 示例单位')}</p><p>↳ PO-101 · {tr('Remaining: 400', '剩余预算：400')}</p><p>↳ {tr('A duplicate request is blocked', '重复提交会被拒付')}</p></div>}
              <div className="terminal-output"><p>↳ {tr('registered supplier · approved purchase order', '已登记供应商 · 已批准采购单')}</p><p>✓ {tr('Your policy decides what moves.', '让规则决定，钱能否转出。')}</p></div>
            </div>
          </div>
          <p className="demo-caption">{tr('Illustrative example. No transaction is sent here. Live results are in the ledger.', '此处仅展示样例，不发送交易。真实结果见账本。')}</p>
        </div>
      </section>
      <section className="launch-card reveal"><div><p className="mono-label">// {tr('READY FOR YOUR FIRST INVOICE', '从第一张发票开始')}</p><h2>{tr('Open your workspace.', '进入你的工作台。')}</h2><p>{tr('Upload invoices, compare agent decisions and follow payment activity in one place.', '上传发票、对照 Agent 的决定，在同一个工作台追踪付款记录。')}</p></div><Magnetic><Link to={workspace} className="site-button">{tr('Open workspace', '进入工作台')} <span aria-hidden>→</span></Link></Magnetic></section>
      <section className="workflow-section" id="workflow"><div className="reveal"><p className="mono-label">// {tr('HOW IT WORKS', '工作流程')}</p><h2>{tr('From request to receipt.', '从请求，到回执。')}</h2></div><div className="workflow-grid">{steps.map(([n, title, text], i) => <article key={n} className="reveal" style={delay(i * 90)}><span className="mono-label">{n}</span><h3>{title}</h3><p>{text}</p></article>)}</div></section>
      <section className="stack-section" id="stack"><div className="reveal"><p className="mono-label">// {tr('BUILDING BLOCKS', '核心能力')}</p><h2>{tr('Explore the', '构建你的')} <span>{tr('workspace.', '付款边界。')}</span></h2><p className="section-copy">{tr('Four connected tools. One record of every decision.', '四个互相连接的工具，让每次决定都有迹可循。')}</p></div>
        <div className="stack-grid">{[
          ['01', tr('Suppliers', '供应商'), tr('Register who can receive payments, and keep payout changes under your control.', '登记可以收款的供应商，收款地址变更由你掌控。'), tr('Registry · Payout · Status', '登记 · 收款地址 · 状态'), '/controls'],
          ['02', tr('Purchase orders', '采购单'), tr('Set a budget and a deadline for each purchase order. Keep spending within its scope.', '为每份采购单设置预算和截止时间，让付款保持在批准范围内。'), tr('Budget · Expiry · Limits', '预算 · 有效期 · 额度'), '/controls'],
          ['03', tr('Agent payments', 'Agent 付款'), tr('Read an invoice, compare agent requests and inspect the rules behind each result.', '读取发票、对照 Agent 的付款请求，检查每个结果背后的规则。'), tr('Invoice · Request · Rules', '发票 · 请求 · 规则'), '/inbox'],
          ['04', tr('Activity & control', '记录与控制'), tr('Follow paid and blocked requests. Queue changes and execute them when ready.', '查看付款与拒付记录，提交变更，并在等待结束后执行。'), tr('Ledger · Timelock · Receipt', '账本 · 时间锁 · 回执'), '/ledger'],
        ].map(([n, title, text, tags, to], i) => <Link className="stack-card reveal" to={to} key={n} style={delay(i * 90)}><span className="stack-number">{n}</span><h3>{title}</h3><p>{text}</p><span className="stack-tags">{tags}</span><strong>{tr('Explore', '打开查看')} →</strong></Link>)}</div>
      </section>
    </main><SiteFooter />
  </div>
}
