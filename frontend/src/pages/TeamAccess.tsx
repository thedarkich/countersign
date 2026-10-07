import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, setAdminToken } from '../api/client'
import { useLang } from '../i18n'
import { SiteHeader, SiteFooter } from '../components/SiteChrome'

export default function TeamAccess() {
  const { tr } = useLang()
  useEffect(() => { document.title = 'Countersign · ' + tr('Team access', '团队访问') }, [tr])
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = params.get('next') === '/controls' ? '/controls' : '/inbox'
  const [token, setToken] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy || !token.trim()) return
    setBusy(true); setError('')
    try {
      if (api.mode === 'live') {
        const response = await fetch('/api/team/attempts?limit=1', { headers: { Authorization: `Bearer ${token.trim()}` }, cache: 'no-store', redirect: 'error' })
        if (response.status === 401 || response.status === 403) { setError(tr('Access token rejected. Check it with the team owner.', '访问令牌无效，请向团队负责人核对。')); return }
        if (!response.ok) throw new Error('Access unavailable')
      }
      setAdminToken(token.trim()); setToken(''); navigate(next, { replace: true })
    } catch { setError(tr('Could not reach the team workspace. Please try again.', '无法连接团队工作台，请稍后重试。')) }
    finally { setBusy(false) }
  }
  return <div className="public-site"><SiteHeader />
    <main className="auth-main" tabIndex={-1}>
      <div className="auth-intro"><p className="mono-label">// {tr('YOUR RULES. EVERY PAYMENT.', '每笔付款，你来定规则。')}</p><h1>{tr('AI checks the invoice.', 'AI 审票。')}<br /><span>{tr('The contract calls the shots.', '合约拍板。')}</span></h1><p>{tr('AI checks invoices. Your contract enforces your payment rules.', 'AI 检查发票，智能合约按你设定的规则放行或拒付。')}</p>
        <div className="auth-flow">{[[tr('Agent requests', 'Agent 提出付款'), tr('Invoice and payment details', '发票与付款信息')], [tr('Rules check', '检查付款规则'), tr('Supplier, purchase order and limits', '供应商、采购单与额度')], [tr('Owner stays in control', '所有者掌控权限'), tr('Wallet signatures and time-locked changes', '钱包签名与延时规则变更')]].map(([title, text], i) => <div className="auth-flow-row" key={title}><span>{i === 2 ? '✓' : '0' + (i + 1)}</span><div><strong>{title}</strong><p>{text}</p></div></div>)}</div>
      </div>
      <section className="auth-card" aria-labelledby="access-title"><p className="mono-label">{tr('TEAM ACCESS', '团队访问')}</p><h2 id="access-title">{tr('Open your workspace.', '进入团队工作台。')}</h2><p className="auth-subtitle">{tr('Use the access token provided by your team owner. Owner actions also require the owner wallet.', '使用团队负责人提供的访问令牌。所有者操作还需要所有者钱包签名。')}</p>
        {api.mode === 'mock' && <p className="auth-message">{tr('Mock preview: any text works. Nothing is sent on-chain.', '模拟预览：输入任意文字即可，不发送链上交易。')}</p>}
        <form className="mt-7" onSubmit={submit}><label className="auth-field">{tr('Team access token', '团队访问令牌')}<input type="password" required autoComplete="off" value={token} onChange={e => setToken(e.target.value)} spellCheck={false} /></label>
          {error && <p className="auth-message" role="alert">{error}</p>}
          <button className="site-button auth-submit" disabled={busy || !token.trim()}>{busy ? tr('Checking access…', '正在验证…') : tr('Open workspace', '进入工作台')} <span aria-hidden>→</span></button>
        </form><p className="auth-access-note">{tr('The ledger and agent history are public. You do not need an account to view them.', '账本和 Agent 历史公开可见，无需创建账户。')}</p><Link className="auth-switch block" to="/ledger">{tr('View public ledger', '查看公开账本')} →</Link>
      </section>
    </main><SiteFooter /></div>
}
