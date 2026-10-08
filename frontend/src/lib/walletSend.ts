import type { Approval, WalletPayment } from './walletApi'

// Once the wallet returns a hash the money has moved. From then on the page only ever reports that hash,
// even after a failed request or a page refresh, so a lost report can never lead to a second payment.

export interface PendingReport {
  paymentId: string
  hash: `0x${string}`
  chainId: number
  wallet: string
  amount: string | null
  payee: string
  label: string
}

export interface ReportStore {
  load(): PendingReport[]
  save(list: PendingReport[]): void
}

const KEY = 'cs_wallet_unreported'

/** Survives a refresh. Storage can be unavailable (private mode); the in-page copy still blocks a resend. */
export function browserStore(): ReportStore {
  return {
    load() {
      try {
        const list = JSON.parse(localStorage.getItem(KEY) ?? '[]')
        return Array.isArray(list) ? list : []
      } catch {
        return []
      }
    },
    save(list) {
      try {
        if (list.length) localStorage.setItem(KEY, JSON.stringify(list))
        else localStorage.removeItem(KEY)
      } catch {
        /* storage unavailable */
      }
    },
  }
}

export function remember(store: ReportStore, report: PendingReport) {
  store.save([...store.load().filter((r) => r.paymentId !== report.paymentId), report])
}

export function forget(store: ReportStore, paymentId: string) {
  store.save(store.load().filter((r) => r.paymentId !== paymentId))
}

type Report = (paymentId: string, hash: string) => Promise<{ payment: WalletPayment }>

/** Report a payment the wallet already sent. Safe to repeat: the server accepts the same hash again. */
export async function record(store: ReportStore, report: PendingReport, sent: Report): Promise<WalletPayment> {
  const { payment } = await sent(report.paymentId, report.hash)
  forget(store, report.paymentId)
  return payment
}

export interface PayDeps {
  approve: () => Promise<Approval>
  send: (tx: Approval['tx']) => Promise<`0x${string}`> // switches chain if needed, then asks the wallet
  sent: Report
  store: ReportStore
  onReporting?: () => void
}

export type PayResult =
  | { status: 'recorded'; payment: WalletPayment }
  | { status: 'unrecorded'; pending: PendingReport; error: unknown }

/**
 * Approve, send once, then report. Errors before the wallet returns a hash propagate (nothing was sent);
 * after it, the hash is kept and the result says the payment still has to be recorded.
 */
export async function payOnce(deps: PayDeps): Promise<PayResult> {
  const { payment, tx } = await deps.approve()
  const hash = await deps.send(tx)
  const report: PendingReport = {
    paymentId: payment.id,
    hash,
    chainId: tx.chain_id,
    wallet: tx.from,
    amount: payment.amount,
    payee: payment.payee,
    label: payment.payee_label,
  }
  remember(deps.store, report) // before anything else can fail
  deps.onReporting?.()
  try {
    return { status: 'recorded', payment: await record(deps.store, report, deps.sent) }
  } catch (error) {
    return { status: 'unrecorded', pending: report, error }
  }
}
