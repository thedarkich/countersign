import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { clearAdminToken, getAdminToken } from '../api/client'
import { useLang } from '../i18n'
import { LangSwitch, ThemeSwitch } from './Toggles'

export function SiteHeader({ workspace = false, landing = false, network, mock = false }: { workspace?: boolean; landing?: boolean; network?: string; mock?: boolean }) {
  const { tr } = useLang()
  const navigate = useNavigate()
  const queries = useQueryClient()
  const authorized = !!getAdminToken()
  const links = workspace
    ? [['/inbox', tr('Inbox', '发票工作台')], ['/ledger', tr('Ledger', '账本')], ['/controls', tr('Controls', '管理控制台')], ['/bounty', tr('Challenge', '挑战防线')]]
    : landing
      ? [['/?section=workflow', tr('Quickstart', '快速开始')], ['/?section=suppliers', tr('Suppliers', '供应商')], ['/?section=orders', tr('Purchase orders', '采购单')], ['/?section=payments', tr('Payments', '付款')], ['/?section=activity', tr('Activity', '记录')]]
      : [['/?section=workflow', tr('How it works', '工作流程')], ['/ledger', tr('Public ledger', '公开账本')], ['/bounty', tr('Challenge', '挑战防线')]]
  return <header className="site-header">
    <div className="site-topbar">
      <Link to="/" className="site-brand" aria-label={tr('Countersign home', 'Countersign 首页')}>Countersign<span className="brand-point">.</span></Link>
      <div className="site-actions">
        <LangSwitch /><ThemeSwitch />
        {authorized && workspace ? <button type="button" className="site-button secondary" onClick={() => { clearAdminToken(); queries.clear(); navigate('/login', { replace: true }) }}>{tr('Sign out', '退出登录')}</button> : <Link className="site-button" to={authorized ? '/inbox' : '/login'}>{tr('Team workspace', '团队工作台')} <span aria-hidden>→</span></Link>}
      </div>
    </div>
    <div className="site-subbar">
      <nav aria-label={tr('Main navigation', '主导航')}>
        {links.map(([to, label]) => <NavLink key={to} to={to} className={({ isActive }) => workspace && isActive ? 'is-active' : ''}>{label}</NavLink>)}
      </nav>
      {workspace && <span className="site-network"><span className="status-dot" />{mock ? tr('Mock data · Simulated workspace', '演示数据 · 模拟工作台') : network}</span>}
    </div>
  </header>
}

export function SiteFooter() {
  const { tr } = useLang()
  return <footer className="site-footer"><Link className="site-brand" to="/">Countersign<span className="brand-point">.</span></Link><span>© 2026 Countersign · {tr('Your rules. Every payment.', '每笔付款，遵循你的规则。')}</span><Link to="/ledger">{tr('View public ledger', '查看公开账本')} →</Link></footer>
}
