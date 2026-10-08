import { useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useLang } from '../i18n'
import { api } from '../api/client'
import { walletApi } from '../lib/walletApi'
import { SiteHeader } from './SiteChrome'

export function Header({ compact = false }: { compact?: boolean }) {
  const { tr } = useLang()
  const loc = useLocation()
  useEffect(() => { window.scrollTo(0, 0); document.title = 'Countersign · ' + loc.pathname.slice(1) }, [loc.pathname])
  const config = useQuery({ queryKey: ['config'], queryFn: api.config, staleTime: 60_000 })
  // the Wallet page pays on its own network (mainnet), independent of the vault's network
  const wallet = useQuery({ queryKey: ['wallet'], queryFn: walletApi.overview, enabled: loc.pathname === '/wallet' && api.mode === 'live', retry: false })
  const net = loc.pathname === '/wallet' ? wallet.data?.network : loc.pathname === '/bounty' ? config.data?.bounty_network ?? config.data?.network : config.data?.network
  const network = net === 'testnet' ? tr('BOT Testnet', 'BOT 测试网') : net === 'mainnet' ? tr('BOT Mainnet', 'BOT 主网') : tr('Connecting…', '连接中…')
  return <div className={compact ? 'site-workspace-header compact' : 'site-workspace-header'}>
    <a className="skip-link" href={'#' + loc.pathname} onClick={e => { e.preventDefault(); document.querySelector<HTMLElement>('main')?.focus() }}>{tr('Skip to content', '跳到正文')}</a>
    <SiteHeader workspace network={network} mock={api.mode === 'mock'} />
  </div>
}
