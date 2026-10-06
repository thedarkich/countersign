import type { ChangeKind, Registry } from '../api/types'

type Lang = 'zh' | 'en'

export const CHANGE_LABEL: Record<ChangeKind, { en: string; zh: string }> = {
  AddVendor: { en: 'Add vendor', zh: '新增供应商' },
  SetPayout: { en: 'Change payout address', zh: '修改收款地址' },
  AddPO: { en: 'Add budget', zh: '新增预算' },
  AddAgent: { en: 'Add agent key', zh: '新增 Agent 密钥' },
  RaiseDailyCap: { en: 'Raise daily cap', zh: '提高每日限额' },
  Unpause: { en: 'Resume payments', zh: '恢复付款' },
  Withdraw: { en: 'Withdraw to owner', zh: '提取到所有者' },
}

/** One line describing a queued change, from the decoded fields the backend sends. */
export function describeChange(kind: ChangeKind, d: Record<string, string | number>, reg: Registry | undefined, lang: Lang, symbol = ''): string {
  const v = reg?.vendors.find((x) => x.id === Number(d.vendor_id))
  const vn = v ? (lang === 'zh' ? v.name_zh : v.name_en) : d.vendor_id != null ? `#${d.vendor_id}` : ''
  const sym = symbol ? ` ${symbol}` : ''
  switch (kind) {
    case 'AddVendor':
      return lang === 'zh' ? `新增供应商 #${d.vendor_id}` : `Add vendor #${d.vendor_id}`
    case 'SetPayout':
      return lang === 'zh' ? `${vn} 的收款地址改为` : `Pay ${vn} at a new address`
    case 'AddPO':
      return lang === 'zh' ? `为 ${vn} 新增预算 ${d.ref ?? `#${d.po_id}`}，上限 ${d.cap}${sym}` : `Budget ${d.ref ?? `#${d.po_id}`} for ${vn}, cap ${d.cap}${sym}`
    case 'AddAgent':
      return lang === 'zh' ? '新增一个 Agent 密钥' : 'Add an agent key'
    case 'RaiseDailyCap':
      return lang === 'zh' ? `每日限额提高到 ${d.new_cap}${sym}` : `Raise the daily cap to ${d.new_cap}${sym}`
    case 'Unpause':
      return lang === 'zh' ? '恢复付款' : 'Resume payments'
    case 'Withdraw':
      return lang === 'zh' ? `提取 ${d.amount}${sym} 到所有者地址` : `Withdraw ${d.amount}${sym} to the owner`
  }
}

/** The address a change would introduce, if any; shown in full because that is what the owner must check. */
export function changeAddress(kind: ChangeKind, d: Record<string, string | number>): string | null {
  if (kind === 'SetPayout') return String(d.new_payout ?? '') || null
  if (kind === 'AddVendor') return String(d.payout ?? '') || null
  if (kind === 'AddAgent') return String(d.agent ?? '') || null
  return null
}
