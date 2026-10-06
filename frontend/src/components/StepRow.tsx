import type { Step, StepName } from '../api/types'
import { useLang } from '../i18n'

// One character per reviewer box, stamped like a department seal on a 会签栏
const STAMP_CHAR: Record<StepName, string> = {
  extract: '读',
  hidden_text: '隐',
  match: '核',
  guard: '审',
  chain: '链',
}

/**
 * The countersign row (会签栏): every step of the pipeline is a box on the form,
 * and each box gets its own small seal when that step signs off.
 */
export function StepRow({ steps }: { steps: Step[] }) {
  const { t, lang } = useLang()
  const label = (n: StepName) =>
    ({ extract: t.step_extract, hidden_text: t.step_hidden_text, match: t.step_match, guard: t.step_guard, chain: t.step_chain })[n]
  return (
    <div>
      <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-3">
        <span className="cond whitespace-nowrap text-lg font-bold">{t.route_title}</span>
        {t.route_sub && <span className="text-sm text-ink2">{t.route_sub}</span>}
      </div>
      <ol className="ruled grid grid-cols-5 overflow-hidden bg-field" aria-label={t.route_title}>
        {steps.map((s, i) => {
          const isLast = i === steps.length - 1
          // department seals are cinnabar; a refusal is signed in ink, like a reviewer's 不同意
          const stampColor = s.name === 'guard' && s.detail === 'refused' ? 'var(--ink)' : 'var(--cinnabar)'
          return (
            <li key={s.name} className={`flex min-h-[5.5rem] flex-col ${isLast ? '' : 'border-r border-rule'}`}>
              <span className="rule-b flex h-7 items-center justify-center whitespace-nowrap px-1 text-center text-[0.8rem] leading-none text-ink2">{label(s.name)}</span>
              <span className="relative flex flex-1 items-center justify-center" aria-live="polite">
                {s.status === 'done' && (
                  <span
                    className="seal-stamp inline-flex h-9 w-9 items-center justify-center rounded-[2px] text-[1.05rem] font-bold"
                    style={{ border: `2px solid ${stampColor}`, color: stampColor, ['--seal-rot' as string]: `${(i % 2 ? 6 : -7)}deg` }}
                    aria-label={`${label(s.name)}: ${t.step_done}`}
                  >
                    {STAMP_CHAR[s.name]}
                  </span>
                )}
                {s.status === 'running' && <span className="step-live h-9 w-9 rounded-[2px] border-2 border-dashed border-ink2" aria-label={`${label(s.name)}: ${t.step_running}`} />}
                {s.status === 'pending' && <span className="h-9 w-9" aria-label={`${label(s.name)}: ${t.step_waiting}`} />}
                {s.status === 'skipped' && (
                  <span className="text-center text-[0.75rem] leading-tight text-ink2">
                    <svg width="42" height="22" aria-hidden className="mx-auto block">
                      <line x1="2" y1="20" x2="40" y2="2" stroke="var(--rule)" strokeWidth="1.5" />
                    </svg>
                    {t.step_skipped}
                  </span>
                )}
                {s.status === 'failed' && <span className="text-xl font-bold text-ink">✕</span>}
              </span>
              {s.status === 'done' && s.detail === 'refused' && (
                <span className="pb-1 text-center text-[0.72rem] font-semibold text-ink">{lang === 'zh' ? '拒绝' : 'refused'}</span>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
