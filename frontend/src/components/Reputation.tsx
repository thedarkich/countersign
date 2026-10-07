import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { AgentHistory } from '../api/types'
import { useLang } from '../i18n'
import { Address, TxLink } from './bits'
import { Icon } from './Icon'

function useReputation() {
  return useQuery({ queryKey: ['reputation'], queryFn: api.reputation, refetchInterval: 10_000 })
}

export function ReputationBadge({ address }: { address: string }) {
  const { tr, lang } = useLang()
  const result = useReputation()
  const agent = result.data?.agents.find(a => a.agent_address.toLowerCase() === address.toLowerCase())
  return <p className={`mt-3 text-xs ${agent?.status === 'suspicious_observed' ? 'text-cinnabar' : 'text-ink2'}`}>
    {agent ? (lang === 'zh' ? agent.status_zh : agent.status_en) : result.isError ? tr('History unavailable', '历史暂不可用') : result.isPending ? tr('Loading history…', '正在加载历史…') : tr('No observed history', '暂无观察历史')}
    {result.data?.coverage.stale && <> · {tr('Last known state', '上次已知状态')}</>}
  </p>
}

export function ReputationPanel() {
  const { tr } = useLang()
  const result = useReputation()
  const coverage = result.data?.coverage
  return <section className="ruled bg-field" aria-label={tr('Payment-agent reputation', '付款 Agent 声誉')}>
    <div className="panel-heading"><div><h2>{tr('Payment-agent history', '付款 Agent 历史')}</h2><p>{tr('Observed proposals and outcomes, with evidence.', '以证据展示已观察到的付款提议与结果。')}</p></div><Icon name="shield" className="text-ink2" /></div>
    {result.isError && <p className="px-6 py-4 text-sm text-cinnabar" role="status">{tr('History could not be refreshed. Any retained records below may be out of date.', '历史更新失败，下方保留的记录可能已过期。')}</p>}
    {!result.data && !result.isError && <p className="p-6 text-sm text-ink2">{tr('Loading agent history…', '正在加载 Agent 历史…')}</p>}
    <div className="agent-activity-grid">{result.data?.agents.map(agent => <HistoryCard key={agent.id} agent={agent} />)}</div>
    {coverage && <div className="border-t border-rule px-6 py-4 text-xs text-ink2 space-y-2">
      <p>{coverage.network === 'testnet' ? tr('BOT testnet', 'BOT 测试网') : tr('BOT mainnet', 'BOT 主网')} · {coverage.chain_id} · <Address value={coverage.contract_address} /> · {coverage.stale ? tr('Stale coverage — review', '覆盖已过期，请审核') : tr('Synced observed history', '已同步观察历史')}</p>
      <p>{tr('Observed blocks', '已观察区块')}: {coverage.observed_from_block ?? '—'}–{coverage.observed_to_block ?? '—'} · {tr('Last sync', '上次同步')}: {coverage.last_sync ? new Date(coverage.last_sync).toLocaleString() : '—'}</p>
      <p>{tr('This configured vault only; discovery depends on the explorer. No flag does not establish safety. Budget blocks, duplicates and errors alone are not fraud.', '仅覆盖当前配置金库；记录发现依赖浏览器。没有标记不代表安全，预算拦截、重复发票和错误本身不代表欺诈。')}</p>
      <details><summary>{tr('Coverage details', '覆盖详情')}</summary><ul className="mt-2 space-y-1">{coverage.gaps.map(gap => <li key={gap} className="break-words font-mono">{gap}</li>)}</ul></details>
    </div>}
  </section>
}

function HistoryCard({ agent }: { agent: AgentHistory }) {
  const { tr, lang } = useLang()
  const c = agent.counts
  const fakePaid = agent.breakdown.filter(b => b.scenario === 'known_attack').reduce((sum, b) => sum + b.counts.confirmed_payments, 0)
  return <article className="agent-row min-w-0">
    <div className="agent-summary"><span className={`agent-avatar ${agent.label}`}><Icon name={agent.label === 'guarded' ? 'shield' : 'agents'} /></span><div className="min-w-0"><h3 className="text-sm font-semibold">{agent.label === 'guarded' ? tr('Guarded agent', '带防护的 Agent') : tr('Naive demo agent', '无防护演示 Agent')}</h3><p className="mt-1 text-xs text-ink2">{lang === 'zh' ? agent.role_zh : agent.role_en}</p></div></div>
    <p className={`mt-4 text-sm font-semibold ${agent.status === 'suspicious_observed' ? 'text-cinnabar' : 'text-ink2'}`}>{lang === 'zh' ? agent.status_zh : agent.status_en}</p>
    <p className="mt-2 text-xs text-ink2"><Address value={agent.agent_address} /> · {agent.active ? tr('Active key', '有效密钥') : tr('Revoked key', '已撤销密钥')}</p>
    <dl className="agent-counts"><div><dt>{tr('Paid', '已支付')}</dt><dd>{c.confirmed_payments}</dd></div><div><dt>{tr('Refused', '已拒绝')}</dt><dd>{c.refusals}</dd></div><div><dt>{tr('Suspicious proposals', '可疑提议')}</dt><dd className={c.suspicious_proposals ? 'text-cinnabar' : ''}>{c.suspicious_proposals}<span className="text-xs text-ink2"> / {c.proposals}</span></dd></div></dl>
    <p className="text-xs text-ink2">{tr('Policy blocks', '规则拦截')}: {c.policy_blocks} · {tr('Errors', '错误')}: {c.errors} · {tr('Observations', '观察数')}: {c.observations}</p>
    <p className="mt-2 text-xs text-ink2">{tr('Known attacks refused', '已知攻击被拒绝')}: {c.known_attack_refusals} / {c.known_attack_attempts} · {tr('Known fake invoices paid to registered vendors', '已知假发票向登记供应商付款')}: {fakePaid}</p>
    <details className="agent-detail"><summary>{tr('Evidence & versions', '证据与版本')}</summary>
      <p>{tr('Observation period', '观察时间段')}: {agent.first_observed_at ? new Date(agent.first_observed_at).toLocaleString() : '—'} — {agent.last_observed_at ? new Date(agent.last_observed_at).toLocaleString() : '—'}</p>
      <p>{tr('Receipt-only / unverified', '仅回执 / 未核验')}: {c.receipt_only} / {c.unverified}</p>
      {agent.breakdown.map((b, i) => <p key={i} className="break-words">{b.source} · {b.scenario} · {Object.entries(b.model_versions).map(([k, v]) => `${k}: ${v}`).join(' · ') || tr('Model unknown', '模型未知')} · {b.guard_version ?? tr('Guard unknown', '守卫未知')} · {b.counts.observations} {tr('observations', '条观察')}</p>)}
      <ul className="mt-3 space-y-3">{agent.recent_observations.map(o => <li key={o.id} className="border-t border-rule pt-3 text-xs">
        <p>{lang === 'zh' ? o.summary_zh : o.summary_en}</p><p>{o.source} · {o.scenario} · {new Date(o.time).toLocaleString()}</p>
        <p>{o.evidence.map(e => e === 'verified_transaction' ? tr('Verified chain receipt', '已核验链上回执') : tr('Application record', '应用记录')).join(' · ')}</p>
        {o.reason_codes.length > 0 && <p className="break-words font-mono">{o.reason_codes.join(' · ')}</p>}
        {o.transaction_url && (api.mode === 'mock' ? <p>{tr('Illustrative receipt · mock data', '示例回执 · 演示数据')}</p> : <TxLink href={o.transaction_url} hash={o.id} label={tr('View receipt', '查看回执')} />)}
      </li>)}</ul>
      <p>{tr('Recent evidence is limited; totals cover all stored observations for this identity. A flag is a reason to review, not proof of fraud.', '近期证据条数有限；总数包含该身份的所有已存观察。标记表示需要审核，不是欺诈定论。')}</p>
    </details>
  </article>
}
