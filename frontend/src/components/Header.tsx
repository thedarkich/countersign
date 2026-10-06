import { NavLink, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useLang } from '../i18n'
import { LangSwitch, ThemeSwitch } from './Toggles'
import { Icon, type IconName } from './Icon'
import { api } from '../api/client'

export function Header({ compact = false }: { compact?: boolean }) {
  const { t, tr } = useLang()
  const loc = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [loc.pathname])
  const config = useQuery({ queryKey: ['config'], queryFn: api.config, staleTime: 60_000 })
  const links: { to: string; label: string; icon: IconName; detail: string }[] = [
    { to: '/ledger', label: t.nav_ledger, icon: 'grid', detail: tr('Overview & activity', '概览与记录') },
    { to: '/inbox', label: t.nav_inbox, icon: 'inbox', detail: tr('Invoice workspace', '发票工作台') },
    { to: '/controls', label: t.nav_controls, icon: 'agents', detail: tr('Agents & policies', 'Agent 与规则') },
    { to: '/bounty', label: t.nav_bounty, icon: 'shield', detail: tr('Test the defenses', '挑战防线') },
  ]
  const current = links.find(l => l.to === loc.pathname) ?? links[0]
  const net = loc.pathname === '/bounty' ? config.data?.bounty_network ?? config.data?.network : config.data?.network
  const network = net === 'testnet' ? tr('BOT Testnet', 'BOT 测试网') : net === 'mainnet' ? tr('BOT Mainnet', 'BOT 主网') : tr('Connecting…', '连接中…')
  return (
    <>
      <a className="skip-link" href={'#' + loc.pathname} onClick={e => { e.preventDefault(); document.querySelector<HTMLElement>('main')?.focus() }}>{tr('Skip to content', '跳到正文')}</a>
      <aside className="workspace-sidebar">
        <NavLink to="/ledger" className="workspace-brand" aria-label="Countersign 会签">
          <span className="brand-symbol"><Icon name="shield" size={22} /></span>
          <span>Countersign<span className="brand-caption">{tr('BOUND BY DESIGN', '让权限有边界')}</span></span>
        </NavLink>
        <p className="nav-eyebrow">{tr('WORKSPACE', '工作空间')}</p>
        <nav aria-label={t.nav_label} className="workspace-nav">
          {links.map(l => <NavLink key={l.to} to={l.to} className={({ isActive }) => `workspace-link ${isActive ? 'is-active' : ''}`}><Icon name={l.icon} /><span>{l.label}<small>{l.detail}</small></span></NavLink>)}
        </nav>
        <div className="sidebar-note"><Icon name="shield" size={19} /><p>{tr('AI proposes.', 'AI 提出付款。')}<br /><strong>{tr('The vault decides.', '金库执行规则。')}</strong></p></div>
        <div className="sidebar-footer"><span className="status-dot" /><span>{network}<small>{api.mode === 'mock' ? tr('Simulated workspace', '模拟工作空间') : tr('Configured network', '当前配置网络')}</small></span></div>
      </aside>
      <header className={`workspace-header ${compact ? 'compact' : ''}`}>
        <NavLink to="/ledger" className="mobile-brand"><span className="brand-symbol"><Icon name="shield" size={18} /></span><span>Countersign</span></NavLink>
        <div className="header-breadcrumb"><span>{tr('Workspace', '工作空间')}</span><span>/</span><strong>{current.label}</strong></div>
        <div className="header-tools">
          <span className="network-pill"><span className="status-dot" />{network}</span>
          {api.mode === 'mock' && <span className="mock-pill">{t.mock_badge}</span>}
          <LangSwitch /><ThemeSwitch />
        </div>
        <nav className="mobile-nav" aria-label={tr('Mobile navigation', '移动导航')}>
          {links.map(l => <NavLink key={l.to} to={l.to} className={({ isActive }) => isActive ? 'is-active' : ''}><Icon name={l.icon} size={16} />{l.label}</NavLink>)}
        </nav>
      </header>
    </>
  )
}
