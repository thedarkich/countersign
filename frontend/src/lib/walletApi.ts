import { getDeviceId } from './device'

// Pay from your own wallet: the account's linked wallet, whitelist, maximum and payments (backend app/api/wallet.py).

export interface WalletPayee {
  id: string
  address: string
  label: string
  created_at?: string
  active_at: number // unix seconds; the address can receive from then on
  active: boolean
}

export interface WalletOverview {
  network: 'mainnet' | 'testnet'
  chain_id: 677 | 968
  explorer_url: string
  payee_delay_seconds: number
  now: number // server clock, unix seconds
  wallet: { address: string; linked_at?: string } | null
  limit: { max: string; pending_max: string | null; pending_at: number | null } | null
  payees: WalletPayee[]
}

export type PaymentStatus = 'approved' | 'sent' | 'confirmed' | 'failed' | 'mismatch' | 'expired'

export interface WalletPayment {
  id: string
  status: PaymentStatus
  payee: string
  payee_label: string
  amount: string
  tx_hash: string | null
  explorer_url: string | null
  block_number: number | null
  detail: string | null
  created_at: string
}

export interface Approval {
  payment: WalletPayment
  tx: { from: `0x${string}`; to: `0x${string}`; value: string; chain_id: 677 | 968 }
}

/** A refusal from the service, with the reason in both languages. */
export class WalletApiError extends Error {
  constructor(
    public status: number,
    public en: string,
    public zh: string,
  ) {
    super(en)
  }
}

async function call<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const res = await fetch('/api/wallet' + path, {
    method,
    credentials: 'same-origin',
    cache: 'no-store',
    headers: { 'X-Device-Id': getDeviceId(), ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new WalletApiError(res.status, data.message_en ?? 'Request could not be completed.', data.message_zh ?? '无法完成请求。')
  return data as T
}

export const walletApi = {
  overview: () => call<WalletOverview>(''),
  challenge: (address: string) => call<{ message: string }>('/challenge', 'POST', { address }),
  link: (address: string, signature: string) => call<{ wallet: { address: string } }>('/link', 'POST', { address, signature }),
  unlink: () => call<{ ok: boolean }>('', 'DELETE'),
  setLimit: (max: string) => call<WalletOverview['limit']>('/limit', 'PUT', { max }),
  addPayee: (address: string, label: string) => call<WalletPayee>('/payees', 'POST', { address, label }),
  removePayee: (id: string) => call<{ ok: boolean }>(`/payees/${encodeURIComponent(id)}`, 'DELETE'),
  approve: (payeeId: string, amount: string) => call<Approval>('/payments', 'POST', { payee_id: payeeId, amount }),
  sent: (id: string, txHash: string) => call<{ payment: WalletPayment }>(`/payments/${encodeURIComponent(id)}/sent`, 'POST', { tx_hash: txHash }),
  payments: () => call<{ payments: WalletPayment[] }>('/payments'),
}
