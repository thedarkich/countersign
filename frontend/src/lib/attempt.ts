import type { Attempt, StepName } from '../api/types'
import type { Strings } from '../i18n/strings'
import type { MarkKind } from '../components/Seal'
import { flagLabel, reasonLabel } from './reasons'

export const isDone = (a: Attempt) => a.status === 'done' || a.status === 'error'

export function attemptMark(a: Attempt): MarkKind {
  if (!isDone(a)) return 'pending'
  if (a.status === 'error') return 'error'
  return (a.outcome ?? 'error') as MarkKind
}

export function outcomeLabel(a: Attempt, t: Strings): string {
  if (!isDone(a)) return a.status
  switch (a.outcome) {
    case 'paid':
      return t.outcome_paid
    case 'blocked':
      return t.outcome_blocked
    case 'refused':
      return t.outcome_refused
    case 'no_invoice':
      return t.outcome_no_invoice
    default:
      return t.outcome_error
  }
}

/** One short reason for a table cell: the chain's reason for blocks, the top flag for refusals. */
export function outcomeReason(a: Attempt, lang: 'zh' | 'en'): string {
  if (a.outcome === 'blocked') return (lang === 'zh' ? a.tx?.reason_label_zh : a.tx?.reason_label_en) ?? reasonLabel(a.tx?.reason, lang)
  if (a.outcome === 'refused') {
    const top = a.flags.find((f) => f.severity === 'high') ?? a.flags[0]
    return top ? flagLabel(top.code, lang) : ''
  }
  return ''
}

export function stepMs(a: Attempt): Partial<Record<StepName, number>> {
  const out: Partial<Record<StepName, number>> = {}
  for (const s of a.steps) {
    if (s.started_at && s.ended_at) out[s.name] = new Date(s.ended_at).getTime() - new Date(s.started_at).getTime()
  }
  return out
}

export const secs = (ms?: number | null) => (ms == null ? '—' : `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`)
