import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { useLang } from '../i18n'
import { Icon } from './Icon'

export function WalletScreeningBadge({ address }: { address: string }) {
  const { tr } = useLang()
  const query = useQuery({ queryKey: ['wallet-security', address], queryFn: () => api.walletSecurity(address), staleTime: 60_000 })
  const verdict = query.data?.checks[0]?.verdict
  return <p className={`mt-2 text-xs ${verdict === 'listed' ? 'text-cinnabar' : 'text-ink2'}`}>
    {verdict === 'listed' ? tr('Scam Sniffer: listed — payments refused', 'Scam Sniffer：已列入名单，拒绝付款') : query.data?.ready && !query.isError ? tr('Scam Sniffer: not listed · not a safety guarantee', 'Scam Sniffer：未列入名单，不代表安全') : tr('Wallet screening unavailable', '钱包筛查暂不可用')}
  </p>
}

export function WalletScreeningPanel() {
  const { tr } = useLang()
  const [input, setInput] = useState('')
  const [address, setAddress] = useState('')
  const query = useQuery({ queryKey: ['wallet-security', address], queryFn: () => api.walletSecurity(address || undefined), refetchInterval: 60_000 })
  const data = query.data
  const verdict = data?.checks[0]?.verdict
  function lookup(event: FormEvent) {
    event.preventDefault()
    if (/^0x[0-9a-fA-F]{40}$/.test(input.trim())) setAddress(input.trim())
  }
  return <section className="ruled bg-field" aria-label={tr('Wallet risk screening', '钱包风险筛查')}>
    <div className="panel-heading"><div><h2>{tr('Wallet risk screening', '钱包风险筛查')}</h2><p>{tr('Scam Sniffer · delayed public address intelligence', 'Scam Sniffer · 延迟公开地址风险数据')}</p></div><Icon name="shield" className="text-ink2" /></div>
    <div className="px-6 pb-6 space-y-3 text-sm">
      <p className={data?.ready && !query.isError ? 'text-jade' : 'text-cinnabar'} role="status">{query.isPending ? tr('Checking feed…', '正在检查数据…') : data?.ready && !query.isError ? tr('Screening active', '风险筛查已启用') : tr('Screening disabled, unavailable or stale — payments held when screening is enabled', '筛查未启用、不可用或已过期；启用时将暂缓付款处理')}</p>
      <p className="text-ink2">{tr('Both agent paths check invoice and proposed payout addresses before signing. A listed address is refused off-chain; this is separate from a vault contract block.', '两个 Agent 路径都会在签名前检查发票和付款提议中的收款地址。命中名单会在链下拒绝，与金库合约拦截分开记录。')}</p>
      <p className="text-ink2">{tr('The free feed has a 7-day publication delay. “Not listed” does not mean safe. Address matches do not prove activity on BOT Chain. Direct transactions outside this backend are not screened by this service.', '免费数据延迟 7 天发布。“未列入名单”不代表安全，地址匹配也不能证明其在 BOT Chain 上有恶意活动。本服务不筛查绕过后端直接发送的交易。')}</p>
      {data && <p className="text-xs text-ink2 break-words">{tr('Addresses', '地址数')}: {data.address_count.toLocaleString()} · {tr('Last checked', '上次检查')}: {data.checked_at ? new Date(data.checked_at).toLocaleString() : '—'} · {tr('Source commit time', '源提交时间')}: {data.source_updated_at ? new Date(data.source_updated_at).toLocaleString() : '—'}</p>}
      {data?.last_refresh_failed && <p className="text-xs text-cinnabar">{tr('Latest refresh failed. The last validated snapshot is retained only within its freshness limit.', '最近一次更新失败，仅在有效期内使用上次验证的数据快照。')}</p>}
      <p className="text-xs"><a className="underline" href="https://github.com/scamsniffer/scam-database" target="_blank" rel="noreferrer">{tr('Source', '来源')}</a> · <a className="underline" href="https://github.com/scamsniffer/scam-database/blob/main/LICENSE" target="_blank" rel="noreferrer">GPL-3.0</a>{data?.revision && <> · <a className="underline font-mono" href={`https://github.com/scamsniffer/scam-database/blob/${data.revision}/blacklist/address.json`} target="_blank" rel="noreferrer">{data.revision.slice(0, 12)}</a></>}</p>
      <form className="flex flex-wrap gap-2" onSubmit={lookup}><label className="flex-1 min-w-0 text-xs">{tr('Check an EVM payout address', '检查 EVM 收款地址')}<input className="field mt-1 font-mono" value={input} onChange={e => setInput(e.target.value)} placeholder="0x…" maxLength={42} spellCheck={false} required pattern="0x[0-9a-fA-F]{40}" /></label><button className="btn btn-ink self-end" disabled={!/^0x[0-9a-fA-F]{40}$/.test(input.trim())}>{tr('Check address', '检查地址')}</button></form>
      {address && <p className={`break-words ${verdict === 'listed' ? 'text-cinnabar' : 'text-ink2'}`} role="status">{address}: {query.isFetching ? tr('Checking…', '正在检查…') : query.isError ? tr('Unable to check', '无法检查') : verdict === 'listed' ? tr('Listed by Scam Sniffer — payment refused', 'Scam Sniffer 名单命中，拒绝付款') : verdict === 'not_listed' ? tr('Not listed in this snapshot. This does not establish safety.', '此快照未收录该地址，不代表安全。') : tr('Feed unavailable; no clearance given.', '数据不可用，未通过风险检查。')}</p>}
      <p className="text-xs text-ink2">{tr('Lookups happen on our server. Addresses and invoice contents are not sent to Scam Sniffer.', '查询在我们的服务器完成，不向 Scam Sniffer 发送地址或发票内容。')}</p>
    </div>
  </section>
}
