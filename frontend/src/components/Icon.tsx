import {
  Activity,
  ArrowRight,
  Bot,
  Check,
  Clock,
  FileText,
  Flag,
  Inbox,
  LayoutGrid,
  Search,
  Shield,
  Upload,
  Wallet,
  type LucideIcon,
} from 'lucide-react'

export type IconName = 'grid' | 'inbox' | 'agents' | 'shield' | 'arrow' | 'wallet' | 'activity' | 'upload' | 'clock' | 'file' | 'search' | 'check' | 'flag'

const icons: Record<IconName, LucideIcon> = {
  grid: LayoutGrid,
  inbox: Inbox,
  agents: Bot,
  shield: Shield,
  arrow: ArrowRight,
  wallet: Wallet,
  activity: Activity,
  upload: Upload,
  clock: Clock,
  file: FileText,
  search: Search,
  check: Check,
  flag: Flag,
}

export function Icon({ name, size = 20, className = '' }: { name: IconName; size?: number; className?: string }) {
  const Cmp = icons[name]
  return <Cmp size={size} strokeWidth={2} className={`shrink-0 ${className}`} aria-hidden="true" />
}
