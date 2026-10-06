import { NavLink, useLocation } from 'react-router-dom'
import { useLang } from '../i18n'
import { BrandSeal } from './Seal'
import { LangSwitch, ThemeSwitch } from './Toggles'
import { api, getAdminToken } from '../api/client'

export function Header({ compact = false }: { compact?: boolean }) {
  const { t } = useLang()
  const loc = useLocation()
  const teamRoute = loc.pathname.startsWith('/inbox') || loc.pathname.startsWith('/controls')
  const showTeam = teamRoute || !!getAdminToken()
  const links = [
    { to: '/bounty', label: t.nav_bounty },
    { to: '/ledger', label: t.nav_ledger },
    ...(showTeam
      ? [
          { to: '/inbox', label: t.nav_inbox },
          { to: '/controls', label: t.nav_controls },
        ]
      : []),
  ]
  const badge = 'shrink-0 whitespace-nowrap rounded-box border border-dashed border-ink2 px-1.5 py-0.5 text-xs text-ink2'
  // phones: brand and switches on top, the page tabs on their own row underneath
  return (
    <header className="guilloche rule-b">
      <div className={`mx-auto flex max-w-6xl flex-wrap items-center gap-x-2 gap-y-1.5 px-4 sm:flex-nowrap sm:gap-x-3 ${compact ? 'py-2' : 'pb-2 pt-3 sm:py-3'}`}>
        <NavLink to="/bounty" className="flex shrink-0 items-center gap-2" aria-label="Countersign 会签">
          <BrandSeal size={compact ? 30 : 34} />
          <span className="cond text-[1.3rem] font-bold leading-none tracking-tight sm:text-[1.35rem]">Countersign</span>
        </NavLink>
        {api.mode === 'mock' && (
          <span className={`ml-1 hidden sm:inline ${badge}`} title="VITE_API_MODE=mock">
            {t.mock_badge}
          </span>
        )}
        <div className="order-2 ml-auto flex shrink-0 items-center gap-1 sm:order-3 sm:ml-0">
          <LangSwitch />
          <ThemeSwitch />
        </div>
        <nav className="order-3 -mx-2 flex w-[calc(100%+1rem)] min-w-0 items-center gap-0.5 overflow-x-auto text-[0.95rem] sm:order-2 sm:mx-0 sm:ml-auto sm:w-auto" aria-label={t.nav_label}>
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              className={({ isActive }) =>
                `shrink-0 whitespace-nowrap rounded-box px-2 py-1 sm:px-2.5 sm:py-1.5 ${isActive ? 'bg-ink text-field' : 'text-ink hover:bg-paper'}`
              }
            >
              {l.label}
            </NavLink>
          ))}
          {api.mode === 'mock' && (
            <span className={`ml-auto mr-2 sm:hidden ${badge}`} title="VITE_API_MODE=mock">
              {t.mock_badge}
            </span>
          )}
        </nav>
      </div>
    </header>
  )
}
