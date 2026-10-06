export type IconName = 'grid' | 'inbox' | 'agents' | 'shield' | 'arrow' | 'wallet' | 'activity' | 'upload' | 'clock' | 'file' | 'search' | 'check' | 'flag'
const paths: Record<IconName, string> = {
  grid: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  inbox: 'M4 4h16l2 12v4H2v-4L4 4Zm-2 12h6l2 3h4l2-3h6M8 8h8M8 12h5',
  agents: 'M12 3v3M9 3h6M5 7h14v13H5zM2 11v5M22 11v5M9 11v2M15 11v2M9 17h6',
  shield: 'M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6l-9-4Zm-4 10 3 3 5-6',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  wallet: 'M3 6h17v15H3V6Zm0 0V3h14v3M15 12h7v5h-7z',
  activity: 'M2 12h4l3-8 6 16 3-8h4',
  upload: 'M12 16V3M7 8l5-5 5 5M3 16v5h18v-5',
  clock: 'M12 8v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
  file: 'M5 2h9l5 5v15H5V2Zm9 0v6h5M8 12h8M8 16h8',
  search: 'm21 21-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
  check: 'm5 12 4 4L19 6',
  flag: 'M5 22V3h14l-3 5 3 5H5',
}
export function Icon({ name, size = 20, className = '' }: { name: IconName; size?: number; className?: string }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={`shrink-0 ${className}`} aria-hidden="true"><path d={paths[name]} /></svg>
}
