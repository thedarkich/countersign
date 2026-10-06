import type { AppConfig, LedgerEvent } from '../api/types'
import { useLang } from '../i18n'
import { Address, TxLink } from './bits'
import { Icon } from './Icon'
import { api } from '../api/client'

/** A bounded view of the event feed, not a global reputation score. */
export function AgentActivity({ config, events }: { config?: AppConfig; events?: LedgerEvent[] }) {
  const { tr } = useLang()
  return <section className="ruled bg-field">
    <div className="panel-heading"><div><h2>{tr('Payment agents', '付款 Agent')}</h2><p>{tr('Two approaches. The same on-chain limits.', '两种处理方式，同一套链上限制。')}</p></div><Icon name="agents" className="text-ink2" /></div>
    <div className="agent-activity-grid">{!events || !config ? <p className="p-6 text-sm text-ink2">{tr('Loading agent activity…', '正在加载 Agent 记录…')}</p> : (['guarded', 'naive'] as const).map(kind => {
      const rows = events.filter(e => e.agent === kind && (e.network ?? config.network) === config.network)
      const flags = rows.filter(e => e.name === 'Blocked' && e.reason === 'PayoutMismatch')
      return <article key={kind} className="agent-row">
        <div className="agent-summary"><span className={`agent-avatar ${kind}`}><Icon name={kind === 'guarded' ? 'shield' : 'agents'} /></span><div className="min-w-0"><h3 className="text-sm font-semibold">{kind === 'guarded' ? tr('Guarded agent', '带防护的 Agent') : tr('Naive agent', '裸奔 Agent')}</h3><p className="mt-1 text-xs text-ink2">{kind === 'guarded' ? tr('Checks invoices before proposing payments', '提出付款前检查发票') : tr('Deliberately unguarded comparison agent', '故意不设防，用作对照')}</p></div></div>
        <dl className="agent-counts">
          <div><dt>{tr('Paid', '已支付')}</dt><dd>{rows.filter(e => e.name === 'Paid').length}</dd></div>
          <div><dt>{tr('Blocked', '已拦截')}</dt><dd>{rows.filter(e => e.name === 'Blocked').length}</dd></div>
          <div><dt>{tr('Redirection flags', '收款地址异常')}</dt><dd className={flags.length ? 'text-cinnabar' : ''}>{flags.length}</dd></div>
        </dl>
        <details className="agent-detail"><summary>{tr('Wallet & evidence', '钱包与证据')}</summary>
          <p>{tr('Configured wallet', '当前配置的钱包')} · <Address value={config.agents[kind]} /></p>
          <p>{flags.length ? tr('A proposed address differed from the vendor registry. This is a suspicious proposal, not proof of fraud.', '提议的地址与供应商登记地址不同。这是可疑提议，不是欺诈定论。') : tr('No redirection flag in this view. This does not establish trust.', '本页暂无收款地址异常记录，这不代表可信。')}</p>
          {flags[0] && <p>{api.mode === 'mock' ? tr('Illustrative event · mock data', '示例记录 · 演示数据') : <TxLink href={flags[0].explorer_url} hash={flags[0].tx_hash} label={tr('View latest evidence', '查看最新证据')} />}</p>}
        </details>
      </article>
    })}</div>
    <p className="border-t border-rule px-6 py-4 text-xs text-ink2">{tr('This network, within the latest 100 returned events. Budget blocks and duplicates are not redirection flags.', '统计返回的最新 100 条记录中属于当前网络的记录。预算或重复发票拦截不算收款地址异常。')}</p>
  </section>
}
