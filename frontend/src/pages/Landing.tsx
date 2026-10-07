import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useLang } from '../i18n'
import { SiteHeader, SiteFooter } from '../components/SiteChrome'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { UsersRound, FileText, ArrowLeftRight, ChartNoAxesColumn, Copy, Check } from 'lucide-react'
import '../landing.css'

export default function LandingPage() {
  const { tr } = useLang()
  const config = useQuery({ queryKey: ['config'], queryFn: api.config, staleTime: 60_000 })
  const preview = api.mode === 'mock' ? tr('MOCK PREVIEW', '模拟预览') : config.data?.network === 'testnet' ? tr('BOT TESTNET PREVIEW', 'BOT 测试网预览') : config.data?.network === 'mainnet' ? tr('BOT MAINNET', 'BOT 主网') : tr('CONNECTING', '正在连接')
  const [params] = useSearchParams()
  const [demo, setDemo] = useState<'request' | 'rules' | 'receipt'>('request')
  const [copied, setCopied] = useState(false)
  const sample = JSON.stringify({ vendorId: 7, poId: 101, amount: '100', invoice: 'INV-001' })
  useEffect(() => {
    document.title = 'Countersign · ' + tr('Your rules. Every payment.', '每笔付款，遵循你的规则。')
    const section = params.get('section')
    if (section && ['workflow', 'stack', 'suppliers', 'orders', 'payments', 'activity'].includes(section)) document.getElementById(section)?.scrollIntoView({ behavior: 'smooth' })
    else window.scrollTo(0, 0)
  }, [params, tr])
  const capabilities = [
    { id: 'suppliers', n: '01', Icon: UsersRound, title: tr('Suppliers', '供应商'), text: tr('Register who can receive payments, and keep payout changes under your control.', '登记可以收款的供应商，让收款地址变更遵循你的规则。'), tags: [tr('Registry', '登记'), tr('Payout', '收款地址'), tr('Status', '状态')], to: '/controls' },
    { id: 'orders', n: '02', Icon: ChartNoAxesColumn, title: tr('Purchase orders', '采购单'), text: tr('Set a budget and a deadline for each purchase order. Keep spending within its approved scope.', '为每份采购单设置预算和截止时间，让付款保持在批准范围内。'), tags: [tr('Budget', '预算'), tr('Expiry', '有效期'), tr('Limits', '额度')], to: '/controls' },
    { id: 'payments', n: '03', Icon: ArrowLeftRight, title: tr('Agent payments', 'Agent 付款'), text: tr('Bring invoices into the workspace, compare agent requests and follow the rules behind each result.', '将发票交给工作台，对照 Agent 的付款请求，检查每个结果背后的规则。'), tags: [tr('Invoice', '发票'), tr('Request', '请求'), tr('Rules', '规则')], to: '/inbox' },
    { id: 'activity', n: '04', Icon: FileText, title: tr('Activity & control', '记录与控制'), text: tr('Follow paid and blocked requests. Queue changes and execute them when the waiting period ends.', '查看付款与拒付记录，提交变更，并在等待结束后执行。'), tags: [tr('Ledger', '账本'), tr('Timelock', '时间锁'), tr('Receipt', '回执')], to: '/ledger' },
  ]
  return <div className="public-site landing-page"><SiteHeader landing />
    <main className="landing-main" id="main-content" tabIndex={-1}>
      <div className="campaign-strip"><span className="mono-label">◆ {preview}</span><strong><span>{tr('Your rules. Every payment.', '每笔付款，遵循你的规则。')}</span> {tr('— a workspace for agents and their payments.', '— 为 Agent 准备的付款工作台。')}</strong><Link to="/login" className="site-button">{tr('Get started', '开始使用')} <span aria-hidden>→</span></Link></div>
      <section className="hero-card">
        <div className="hero-copy"><p className="mono-label">// {tr('HAVE AN AGENT', '让 AGENT 开始工作')}</p>
          <h1>{tr('Give agents', '让 Agent 放手工作，')}<br /><span>{tr('payment boundaries.', '让每笔付款有边界。')}</span></h1>
          <p>{tr('A security workspace for AI invoice payments. Register suppliers, approve purchase orders and set budgets. The vault checks each request before money moves.', '为 AI 发票付款提供安全工作台。登记供应商、批准采购单、设置预算。每次请求，都由金库先检查，再决定是否付款。')}</p>
          <div className="hero-actions"><Link to="/ledger" className="site-button">{tr('View live ledger', '查看实时账本')} <span aria-hidden>→</span></Link><Link to="/login" className="site-button secondary">{tr('Quickstart', '快速开始')}</Link></div>
        </div>
        <div className="hero-demo"><p className="mono-label">◆ {tr('ONE PAYMENT FLOW — PICK A STEP', '一笔付款的流程 — 选择一个步骤')}</p>
          <div className="demo-options" role="group" aria-label={tr('Payment demonstration steps', '付款演示步骤')}>
            {(['request', 'rules', 'receipt'] as const).map((v, i) => <button key={v} aria-pressed={demo === v} onClick={() => { setDemo(v); setCopied(false) }}>{['↗', '◇', '✓'][i]} {v === 'request' ? tr('Request', '付款请求') : v === 'rules' ? tr('Rules', '规则检查') : tr('Receipt', '执行回执')}</button>)}
          </div>
          <div className="demo-context"><span>◇ {tr('Supplier 7', '供应商 7')}</span><span>▤ PO-101</span><span>◈ {tr('Virtual funds', '虚拟资金')}</span></div>
          <div className="terminal-card"><div className="terminal-bar"><div className="terminal-lights"><i /><i /><i /></div><span>Countersign</span><span className="terminal-badge">{tr('EXAMPLE', '演示样例')}</span><button type="button" title={tr('Copy sample request', '复制请求样例')} aria-label={tr('Copy sample request', '复制请求样例')} onClick={async () => { try { await navigator.clipboard.writeText(sample); setCopied(true) } catch { setCopied(false) } }}>{copied ? <Check size={14} /> : <Copy size={14} />}</button></div>
            <div className="terminal-body" aria-live="polite">
              <p className="terminal-comment">{demo === 'request' ? tr('An agent submits a payment request.', 'Agent 提交一笔付款请求。') : demo === 'rules' ? tr('Every check must pass before payment.', '每一项规则都通过，才能付款。') : tr('The receipt explains what happened.', '回执记录发生了什么。')}</p>
              {demo === 'request' ? <pre><span className="terminal-prompt">{'>'} pay </span>{sample}</pre> : demo === 'rules' ? <div className="terminal-checks"><p>✓ {tr('Supplier 7 is active', '供应商 7 已登记且有效')}</p><p>✓ {tr('PO-101 belongs to supplier 7', 'PO-101 归属于供应商 7')}</p><p>✓ {tr('100 is within the approved budget', '100 在批准预算内')}</p><p>✓ {tr('This invoice has not been paid', '这张账单尚未支付')}</p></div> : <div className="terminal-checks"><p>✓ {tr('Paid · 100 example units', '已支付 · 100 示例单位')}</p><p>↳ PO-101 · {tr('Remaining: 400', '剩余预算：400')}</p><p>↳ {tr('A duplicate request is blocked', '重复提交会被拒付')}</p></div>}
              <div className="terminal-output"><p>↳ {tr('registered supplier · approved purchase order', '已登记供应商 · 已批准采购单')}</p><p>✓ {tr('Your policy decides what moves.', '让规则决定，钱能否转出。')}</p></div>
            </div>
          </div>
          <p className="demo-caption">{tr('Illustrative example · No transaction is sent here. Live results are in the ledger.', '流程示例 · 此处不发送交易。真实结果见账本。')}</p>
        </div>
      </section>
      <section className="launch-card" id="workflow"><div><p className="mono-label">// {tr('NEED A PAYMENT WORKSPACE', '准备好你的付款工作台')}</p><h2>{tr('Open your workspace.', '进入你的工作台。')}</h2><p>{tr('Team access connects invoices, agent decisions and payment records. Everyone can inspect the public ledger and agent history.', '团队工作台连接发票、Agent 决策与付款记录。所有人都能查看公开账本和 Agent 历史。')}</p></div><Link to="/inbox" className="site-button">{tr('Open workspace', '进入工作台')} <span aria-hidden>→</span></Link></section>
      <section className="stack-section" id="stack"><p className="mono-label">// {tr('BUILDING BLOCKS', '核心能力')}</p><h2>{tr('Explore the', '探索你的')} <span>{tr('workspace.', '付款工作台。')}</span></h2><p className="section-copy">{tr('Four building blocks for every payment. Pick one to explore its controls and records.', '四项能力，串起每笔付款。选择一项，查看它的规则与记录。')}</p>
        <div className="stack-grid">{capabilities.map(({ id, n, Icon, title, text, tags, to }) => <Link className="stack-card" id={id} to={to} key={n}><div className="stack-card-top"><span className="stack-number">{n}</span><span className="stack-icon"><Icon size={16} strokeWidth={1.6} /></span></div><h3>{title}</h3><p>{text}</p><span className="stack-tags">{tags.map(tag => <span key={tag}>{tag}</span>)}</span><strong>{tr('Explore workspace', '打开工作台')} →</strong></Link>)}</div>
      </section>
    </main><SiteFooter />
  </div>
}
