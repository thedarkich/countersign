// Contract Reason enum (docs/SPEC.md §2.2), in order. Index = on-chain value.
export const REASONS = [
  'None',
  'Paused',
  'ZeroAmount',
  'UnknownVendor',
  'VendorInactive',
  'PayoutMismatch',
  'UnknownPO',
  'POVendorMismatch',
  'POExpired',
  'OverBudget',
  'DuplicateInvoice',
  'OverDailyCap',
  'InsufficientFunds',
] as const
export type ReasonName = (typeof REASONS)[number]

export const REASON_LABELS: Record<string, { en: string; zh: string }> = {
  Paused: { en: 'Paused', zh: '已暂停' },
  ZeroAmount: { en: 'Zero amount', zh: '金额为零' },
  UnknownVendor: { en: 'Unknown vendor', zh: '未知供应商' },
  VendorInactive: { en: 'Vendor inactive', zh: '供应商已停用' },
  PayoutMismatch: { en: 'Payout mismatch', zh: '收款地址不符' },
  UnknownPO: { en: 'Unknown PO', zh: '采购单不存在' },
  POVendorMismatch: { en: 'PO belongs to another vendor', zh: '采购单不属于该供应商' },
  POExpired: { en: 'PO expired', zh: '采购单已过期' },
  OverBudget: { en: 'Over budget', zh: '超出预算' },
  DuplicateInvoice: { en: 'Duplicate invoice', zh: '重复发票' },
  OverDailyCap: { en: 'Over daily cap', zh: '超出每日限额' },
  InsufficientFunds: { en: 'Insufficient funds', zh: '金库余额不足' },
}

export function reasonLabel(reason: string | null | undefined, lang: 'zh' | 'en'): string {
  if (!reason) return ''
  const l = REASON_LABELS[reason]
  return l ? l[lang] : reason
}

// Off-chain guard flag codes (SPEC §3.5)
export const FLAG_LABELS: Record<string, { en: string; zh: string }> = {
  HIDDEN_TEXT: { en: 'Hidden text in the file', zh: '文件里有隐藏文字' },
  PAYOUT_CHANGED: { en: 'Invoice asks to pay a different address', zh: '发票要求付到另一个地址' },
  LOOKALIKE_VENDOR: { en: 'Vendor name imitates a real vendor', zh: '供应商名称冒充真实供应商' },
  UNKNOWN_PO: { en: 'Purchase order not found', zh: '找不到采购单' },
  PO_VENDOR_MISMATCH: { en: 'PO belongs to another vendor', zh: '采购单不属于该供应商' },
  OVER_BUDGET: { en: 'Amount exceeds the remaining budget', zh: '金额超出剩余预算' },
  DUPLICATE_INVOICE: { en: 'This invoice was already paid', zh: '这张发票已经付过款' },
  INSTRUCTION_TO_AGENT: { en: 'Text gives instructions to the AI', zh: '文字在给 AI 下指令' },
  PAYMENT_DETAILS_CHANGE: { en: 'Tries to change payment details', zh: '试图修改收款信息' },
  VENDOR_IMPERSONATION: { en: 'Impersonates a vendor', zh: '冒充供应商' },
  URGENCY_PRESSURE: { en: 'Pressure to pay urgently', zh: '催促立即付款' },
  AMOUNT_ANOMALY: { en: 'Unusual amount', zh: '金额异常' },
}
export function flagLabel(code: string, lang: 'zh' | 'en'): string {
  const l = FLAG_LABELS[code]
  return l ? l[lang] : code
}
