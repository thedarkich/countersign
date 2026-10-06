export function shortAddr(a?: string | null, lead = 6, tail = 4): string {
  if (!a) return '—'
  if (a.length <= lead + tail + 2) return a
  return `${a.slice(0, lead)}…${a.slice(-tail)}`
}

export function fmtAmount(v?: string | number | null, symbol?: string): string {
  if (v === null || v === undefined || v === '') return '—'
  const n = typeof v === 'number' ? v : Number(v)
  if (Number.isNaN(n)) return String(v)
  const s = n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 })
  return symbol ? `${s} ${symbol}` : s
}

export function fmtInt(n?: number | null): string {
  if (n === null || n === undefined) return '0'
  return n.toLocaleString('en-US')
}

export function timeAgo(iso: string, lang: 'zh' | 'en'): string {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000))
  if (s < 60) return lang === 'zh' ? `${s} 秒前` : `${s}s ago`
  const m = Math.round(s / 60)
  if (m < 60) return lang === 'zh' ? `${m} 分钟前` : `${m} min ago`
  const h = Math.round(m / 60)
  if (h < 48) return lang === 'zh' ? `${h} 小时前` : `${h} h ago`
  return new Date(iso).toLocaleDateString(lang === 'zh' ? 'zh-CN' : 'en-GB')
}

export function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function pct(x?: number | null): string {
  if (x === null || x === undefined) return '—'
  return `${Math.round(x * 100)}%`
}

export const isAddress = (a: string) => /^0x[0-9a-fA-F]{40}$/.test(a.trim())

/** The public bounty link for the QR code. Works whether the base is a folder or an index.html. */
export function bountyUrl(base?: string | null): string {
  if (!base) return ''
  const b = base.replace(/#.*$/, '')
  if (/\.html?$/i.test(b)) return `${b}#/bounty`
  return `${b.replace(/\/+$/, '')}/#/bounty`
}

export const addressUrl = (explorer: string, a: string) => `${explorer.replace(/\/+$/, '')}/address/${a}`
