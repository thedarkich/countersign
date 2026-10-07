import type { Attempt } from '../api/types'
import { useLang } from '../i18n'
import { isDone } from '../lib/attempt'
import { fmtAmount } from '../lib/format'
import { flagLabel, reasonLabel } from '../lib/reasons'
import { Address, TxLink } from './bits'

// The vault's rules in the order Countersign.sol checks them (pay → _check); each covers one or more Reason values.
const CHECKS = [
  { reasons: ['Paused', 'ZeroAmount'], en: 'Vault open, amount above zero', zh: '金库未暂停，金额大于零' },
  { reasons: ['UnknownVendor', 'VendorInactive'], en: 'Vendor is registered and active', zh: '供应商已登记且有效' },
  { reasons: ['PayoutMismatch'], en: 'Pays the registered payout address', zh: '付到登记的收款地址' },
  { reasons: ['UnknownPO', 'POVendorMismatch', 'POExpired'], en: "Valid purchase order for this vendor", zh: '采购单有效且属于该供应商' },
  { reasons: ['OverBudget'], en: 'Within the purchase-order budget', zh: '未超出采购单预算' },
  { reasons: ['DuplicateInvoice'], en: 'Invoice was not paid before', zh: '这张发票没有付过款' },
  { reasons: ['OverDailyCap', 'InsufficientFunds'], en: 'Within the daily cap and vault balance', zh: '未超出每日限额和金库余额' },
]

type CheckState = 'pass' | 'fail' | 'skip'

function checkStates(a: Attempt): CheckState[] | null {
  if (!a.tx) return null
  if (a.tx.event === 'Paid') return CHECKS.map(() => 'pass')
  const failed = CHECKS.findIndex((c) => c.reasons.includes(a.tx?.reason ?? ''))
  return CHECKS.map((_, i) => (failed < 0 ? 'skip' : i < failed ? 'pass' : i === failed ? 'fail' : 'skip'))
}

const MARK: Record<CheckState, { glyph: string; color: string }> = {
  pass: { glyph: '✓', color: 'var(--jade)' },
  fail: { glyph: '✕', color: 'var(--cinnabar)' },
  skip: { glyph: '·', color: 'var(--ink-2)' },
}

/**
 * Who decided what: the AI agent only reads the invoice and proposes a payment;
 * the vault contract checks its own rules on chain and pays or blocks.
 */
export function Decision({ attempt: a, symbol }: { attempt: Attempt; symbol: string }) {
  const { tr, lang } = useLang()
  const done = isDone(a)
  const p = a.proposal
  const top = a.flags.find((f) => f.severity === 'high') ?? a.flags[0]
  const states = checkStates(a)
  const proposed = !!a.tx || (done && a.outcome !== 'refused' && a.outcome !== 'no_invoice' && a.status !== 'error' && !!p?.pay_to)

  let agentLine: string
  if (!done) agentLine = tr('Reading the invoice…', '正在读取发票…')
  else if (a.outcome === 'no_invoice') agentLine = tr('Not an invoice, so there is nothing to pay.', '这不是发票，没有需要付款的内容。')
  else if (a.outcome === 'refused') agentLine = tr('Refused. It did not propose a payment.', '拒绝了，没有提出付款。')
  else if (a.status === 'error') agentLine = tr('Stopped before making a proposal.', '提出付款前就停止了。')
  else if (a.agent === 'naive') agentLine = tr('Proposed what the invoice says, without review.', '照发票原样提出付款，没有审核。')
  else agentLine = tr('Checked the invoice and proposed a payment.', '检查了发票，提出付款。')

  return (
    <section aria-label={tr('Who decided what', '谁做了什么决定')} className="overflow-hidden ruled text-sm">
      <div className="border-b border-rule p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-ink2">{tr('1 · AI agent reads and proposes', '1 · AI Agent 读票、提议')}</p>
        <p className="mt-1.5 font-semibold leading-snug">{agentLine}</p>
        {done && a.outcome === 'refused' && top && (
          <p className="mt-1 leading-snug text-ink2">
            <strong className="text-ink">{flagLabel(top.code, lang)}.</strong> {lang === 'zh' ? top.detail_zh : top.detail_en}
          </p>
        )}
        {proposed && p && (
          <p className="mt-1 leading-snug">
            {tr('Pay ', '付 ')}
            <span className="num font-mono">{p.amount ? `${fmtAmount(p.amount)} ${symbol}` : '—'}</span>
            {tr(' to ', ' 到 ')}
            <Address value={p.pay_to} />
          </p>
        )}
        {done && a.outcome !== 'refused' && a.flags.length > 0 && (
          <p className="mt-1 text-xs text-ink2">{tr(`${a.flags.length} warning(s) noted along the way.`, `记录了 ${a.flags.length} 条提示。`)}</p>
        )}
        <p className="mt-2 text-xs leading-snug text-ink2">{tr('The agent cannot move money. It can only ask the vault.', 'Agent 不能直接动钱，只能向金库提出请求。')}</p>
      </div>

      <div className="p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-ink2">{tr('2 · Vault contract checks and decides', '2 · 金库合约检查、拍板')}</p>
        {states && a.tx ? (
          <>
            <p className="mt-1.5 font-semibold leading-snug" style={{ color: a.tx.event === 'Paid' ? 'var(--jade)' : 'var(--cinnabar)' }}>
              {a.tx.event === 'Paid'
                ? tr('Every rule passed. Paid on chain.', '所有规则通过，链上已付款。')
                : `${tr('Blocked on chain: ', '链上拒付：')}${(lang === 'zh' ? a.tx.reason_label_zh : a.tx.reason_label_en) ?? reasonLabel(a.tx.reason, lang)}`}
            </p>
            <ol className="mt-1.5 space-y-0.5">
              {CHECKS.map((c, i) => (
                <li key={c.en} className={`flex gap-2 leading-snug ${states[i] === 'skip' ? 'text-ink2' : ''}`}>
                  <span className="w-3 shrink-0 text-center font-bold" style={{ color: MARK[states[i]].color }} aria-hidden>
                    {MARK[states[i]].glyph}
                  </span>
                  <span>
                    {lang === 'zh' ? c.zh : c.en}
                    {states[i] === 'skip' && <span className="sr-only"> ({tr('not checked', '未检查')})</span>}
                    {states[i] === 'fail' && <span className="sr-only"> ({tr('failed', '未通过')})</span>}
                  </span>
                </li>
              ))}
            </ol>
            <p className="mt-2 text-xs">
              <TxLink href={a.tx.explorer_url} hash={a.tx.hash} label={tr('Transaction on BOT Chain', 'BOT Chain 上的交易')} />
            </p>
          </>
        ) : (
          <p className="mt-1.5 leading-snug text-ink2">
            {!done
              ? tr('Waiting for the agent’s proposal.', '等待 Agent 的付款请求。')
              : proposed
                ? tr('No transaction was recorded.', '没有记录到交易。')
                : tr('Not asked. Nothing was sent to the contract, so no money moved.', '没有收到请求，没有交易发往合约，资金没有移动。')}
          </p>
        )}
      </div>
    </section>
  )
}
