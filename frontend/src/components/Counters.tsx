import type { StatBlock } from '../api/types'
import { useLang } from '../i18n'
import { fmtAmount, fmtInt } from '../lib/format'

type Tile = { key: string; label: string; value: string; tone?: 'jade' | 'cinnabar' | 'ink'; note?: string }

export function useTiles(s: StatBlock | undefined, symbol: string): Tile[] {
  const { t } = useLang()
  if (!s) return []
  return [
    { key: 'attempts', label: t.c_attempts, value: fmtInt(s.attempts) },
    { key: 'people', label: t.c_people, value: fmtInt(s.people) },
    { key: 'guard', label: t.c_guard, value: fmtInt(s.guard_catches) },
    { key: 'blocks', label: t.c_blocks, value: fmtInt(s.chain_blocks), tone: 'cinnabar' },
    { key: 'fooled_g', label: t.c_fooled_g, value: fmtInt(s.ai_fooled.guarded) },
    { key: 'fooled_n', label: t.c_fooled_n, value: fmtInt(s.ai_fooled.naive) },
    { key: 'lost', label: t.c_lost, value: fmtAmount(s.money_lost), tone: 'jade', note: symbol },
  ]
}

/** Totals laid out like the summary line at the foot of a ledger page. */
export function Counters({ stats, symbol, size = 'md' }: { stats?: StatBlock; symbol: string; size?: 'md' | 'stage' }) {
  const tiles = useTiles(stats, symbol)
  if (!stats) return <div className="h-24 animate-pulse rounded-box bg-paper2" aria-hidden />
  const stage = size === 'stage'
  return (
    <dl className={`grid ${stage ? 'grid-cols-4 gap-px' : 'grid-cols-2 gap-px sm:grid-cols-4'} overflow-hidden ruled bg-rule`}>
      {tiles.map((x) => {
        const isLost = x.key === 'lost'
        return (
          <div key={x.key} className={`flex flex-col justify-between bg-field ${stage ? 'px-5 py-[clamp(0.6rem,1.8vh,1.25rem)]' : 'p-3'} ${isLost ? 'col-span-2' : ''}`}>
            <dt className={`${stage ? 'text-[clamp(0.95rem,1.9vh,1.2rem)]' : 'text-[0.82rem]'} leading-snug text-ink2`}>{x.label}</dt>
            <dd
              className={`num cond-x font-bold leading-none ${stage ? (isLost ? 'mt-1 text-[clamp(3.2rem,8.6vh,6rem)]' : 'mt-1 text-[clamp(2.8rem,7.2vh,5rem)]') : 'mt-1 text-[2.3rem]'}`}
              style={{ color: x.tone === 'jade' ? 'var(--jade)' : x.tone === 'cinnabar' ? 'var(--cinnabar)' : 'var(--ink)' }}
            >
              {x.value}
              {x.note && <span className={`ml-1.5 align-baseline font-semibold ${stage ? 'text-2xl' : 'text-sm'}`}>{x.note}</span>}
            </dd>
          </div>
        )
      })}
    </dl>
  )
}
