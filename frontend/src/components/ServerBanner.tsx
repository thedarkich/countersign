import { useLang } from '../i18n'
import { useServerDown } from '../lib/net'

/** A thin strip at the top of every screen while the backend is unreachable. Queries keep retrying underneath. */
export function ServerBanner() {
  const down = useServerDown()
  const { tr } = useLang()
  if (!down) return null
  return (
    <div role="status" className="fixed inset-x-0 top-0 z-50 border-b border-cinnabar bg-[var(--cinnabar-wash)] px-4 py-1.5 text-center text-sm font-semibold text-cinnabar">
      <span className="step-live mr-2 inline-block h-2 w-2 rounded-full bg-cinnabar align-middle" aria-hidden />
      {tr("Can't reach the server. Retrying…", '连不上服务器，正在重试…')}
    </div>
  )
}
