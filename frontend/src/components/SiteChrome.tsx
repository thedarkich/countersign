import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { clearAdminToken, getAdminToken } from '../api/client'
import { landingFor, onTeam, useAuth } from '../lib/auth'
import { useLang } from '../i18n'
import { LangSwitch, ThemeSwitch } from './Toggles'

export function SiteHeader({ workspace = false, network, mock = false }: { workspace?: boolean; network?: string; mock?: boolean }) {
  const { tr } = useLang()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const queries = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const signedIn = !!user || !!getAdminToken()
  async function signOut() {
    setBusy(true); setError('')
    try {
      if (user) await logout()
      clearAdminToken()
      queries.clear()
      navigate('/login', { replace: true })
    } catch { setError(tr('Could not sign out. Please retry.', '退出未完成，请重试。')) }
    finally { setBusy(false) }
  }
  const team = onTeam(user)
  const links = (workspace
    ? [['/inbox', tr('Inbox', '发票工作台')], ['/wallet', tr('Wallet', '钱包')], ['/ledger', tr('Ledger', '账本')], ['/controls', tr('Controls', '管理控制台')], ['/bounty', tr('Challenge', '挑战防线')]]
    : [['/?section=workflow', tr('How it works', '工作流程')], ['/?section=stack', tr('Building blocks', '核心能力')], [landingFor(user, '/inbox'), tr('Workspace', '工作台')]]
  ).filter(([to]) => team || to !== '/controls')
  return <header className="site-header">
    <div className="site-topbar">
      <Link to="/" className="site-brand" aria-label={tr('Countersign home', 'Countersign 首页')}><img src="/countersign-mark.png" alt="" className="brand-mark" /><span>Countersign</span></Link>
      <div className="site-actions">
        <LangSwitch /><ThemeSwitch />
        {signedIn ? <>
          <span className="account-label" title={user?.email}>{user ? user.name : tr('Team token', '团队令牌')}</span>
          {workspace ? <button type="button" className="site-button secondary" disabled={busy} onClick={() => void signOut()}>{busy ? tr('Signing out…', '正在退出…') : tr('Sign out', '退出登录')}</button>
            : <Link className="site-button" to={landingFor(user, '/inbox')}>{tr('Open workspace', '进入工作台')} <span aria-hidden>→</span></Link>}
        </> : <>
          <Link className="site-signin" to="/login">{tr('Sign in', '登录')}</Link>
          <Link className="site-button" to="/signup">{tr('Get started', '开始使用')} <span aria-hidden>→</span></Link>
        </>}
      </div>
    </div>
    <div className="site-subbar">
      <nav aria-label={tr('Main navigation', '主导航')}>
        {links.map(([to, label]) => <NavLink key={to} to={to} className={({ isActive }) => workspace && isActive ? 'is-active' : ''}>{label}</NavLink>)}
      </nav>
      {workspace && <span className="site-network"><span className="status-dot" />{mock ? tr('Mock data · Simulated workspace', '演示数据 · 模拟工作台') : network}</span>}
    </div>
    {error && <p className="site-error" role="alert">{error}</p>}
  </header>
}

export function SiteFooter() {
  const { tr } = useLang()
  return <footer className="site-footer"><Link className="site-brand" to="/"><img src="/countersign-mark.png" alt="" className="brand-mark" /><span>Countersign</span></Link><span>© 2026 Countersign · {tr('Your rules. Every payment.', '每笔付款，遵循你的规则。')}</span><Link to="/ledger">{tr('View public ledger', '查看公开账本')} →</Link></footer>
}
