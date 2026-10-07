// Shapes mirror docs/SPEC.md §3.9. Amounts are human-unit decimal strings.

export type AgentKind = 'guarded' | 'naive'
export type AttemptStatus = 'queued' | 'extracting' | 'checking' | 'deciding' | 'sending' | 'done' | 'error'
export type Outcome = 'paid' | 'blocked' | 'refused' | 'no_invoice' | 'error'
export type Source = 'bounty' | 'seed' | 'team' | 'batch'

export type StepName = 'extract' | 'hidden_text' | 'match' | 'guard' | 'chain'
export interface Step {
  name: StepName
  status: 'pending' | 'running' | 'done' | 'skipped' | 'failed'
  started_at?: string | null
  ended_at?: string | null
  detail?: string | null
}

export interface Flag {
  code: string
  severity: 'high' | 'medium' | 'low'
  detail_en: string
  detail_zh: string
}

export interface Extraction {
  is_invoice: boolean
  vendor_name: string | null
  invoice_number: string | null
  invoice_date: string | null
  due_date: string | null
  currency: string | null
  amount_total: number | null
  po_reference: string | null
  payee_address: string | null
  notes_to_payer: string | null
  language: 'zh' | 'en' | 'mixed'
  visible_text: string
}

export interface HiddenSpan {
  text: string
  reason: 'near_white' | 'tiny_font' | 'off_page' | 'zero_area'
  bbox: [number, number, number, number] // x0, y0, x1, y1 in PDF points
  page: number
}
export interface HiddenText {
  has_hidden_text: boolean
  page_size: [number, number] | null // width, height in PDF points
  spans: HiddenSpan[]
  diff_words: string[]
}

export interface Proposal {
  vendor_id: number | null
  vendor_name: string | null
  pay_to: string | null
  registry_payout: string | null
  po_id: number | null
  po_ref: string | null
  amount: string | null
  invoice_hash: string | null
}

export interface TxInfo {
  hash: string
  explorer_url: string
  event: 'Paid' | 'Blocked'
  reason: string | null // contract Reason name, e.g. "PayoutMismatch"
  reason_label_en: string | null
  reason_label_zh: string | null
  network?: 'mainnet' | 'testnet' // set when it differs between bounty and team transactions
}

export interface Attempt {
  id: string
  status: AttemptStatus
  outcome: Outcome | null
  agent: AgentKind
  source: Source
  nickname?: string | null
  input_kind?: 'pdf' | 'image' | 'text'
  file_name?: string | null
  preview_url?: string | null
  steps: Step[]
  extraction: Extraction | null
  hidden_text: HiddenText | null
  flags: Flag[]
  proposal: Proposal | null
  tx: TxInfo | null
  ai_fooled: boolean
  created_at: string
  latency_ms?: number | null
}

export interface StatBlock {
  attempts: number
  people: number
  guard_catches: number
  ai_fooled: { guarded: number; naive: number }
  chain_blocks: number
  paid_real_vendor_on_fake_invoice: string
  money_lost: string
}
export interface Stats {
  outside: StatBlock
  seed: StatBlock
  since: string | null
}

export interface LeaderboardEntry {
  nickname: string
  agent: AgentKind
  attempt_id: string
  created_at: string
  summary_en: string
  summary_zh: string
}

export type LedgerKind = 'paid' | 'blocked' | 'changes' | 'all'
export interface LedgerEvent {
  id: string
  name: 'Paid' | 'Blocked' | 'ChangeQueued' | 'ChangeExecuted' | 'ChangeCancelled' | 'VendorDeactivated' | 'POClosed' | 'AgentRevoked' | 'DailyCapLowered' | 'Paused'
  tx_hash: string
  explorer_url: string
  block_time: string
  agent: AgentKind | null
  vendor_id: number | null
  vendor_name: string | null
  amount: string | null
  pay_to: string | null
  reason: string | null
  reason_label_en: string | null
  reason_label_zh: string | null
  summary_en: string | null
  summary_zh: string | null
  network?: 'mainnet' | 'testnet'
}

export interface Vendor {
  id: number
  name_en: string
  name_zh: string
  payout: string
  active: boolean
}
export interface PO {
  po_id: number
  ref: string
  vendor_id: number
  cap: string
  remaining: string
  expiry: string
  period_days: number
  closed: boolean
}
export type ChangeKind = 'AddVendor' | 'SetPayout' | 'AddPO' | 'AddAgent' | 'RaiseDailyCap' | 'Unpause' | 'Withdraw'
export interface PendingChange {
  id: string
  kind: ChangeKind
  decoded: Record<string, string | number>
  eta: string
  ready: boolean
}
export interface Registry {
  vendors: Vendor[]
  pos: PO[]
  pending_changes: PendingChange[]
  daily_cap: string
  remaining_today: string
  paused: boolean
  vault_balance: string
  agents?: {
    address: string
    label: AgentKind | string
    active: boolean
    balance?: string // native BOT the key holds; 0 when gas is sponsored
    gas?: 'sponsored' | 'self' // sponsored = BOT Chain paymaster pays this key's gas
  }[]
}

export interface AppConfig {
  network: 'testnet' | 'mainnet'
  chain_id: number
  rpc_url: string
  explorer_url: string
  contract_address: string
  token: { address: string; symbol: string; decimals: number }
  owner_address: string
  agents: { guarded: string; naive: string }
  public_base_url: string
  timelock_seconds?: number
  bounty_network?: 'mainnet' | 'testnet' // where public bounty attempts are sent, if not `network`
}

export interface EvalSide {
  catch: number
  false_alarm: number
  catch_ci?: [number, number]
  false_alarm_ci?: [number, number]
}
export interface EvalResults {
  created_at?: string
  n_train_attacks?: number
  n_heldout_attacks?: number
  n_heldout_clean?: number
  v1?: EvalSide
  v2?: EvalSide
  split?: string
}

/** Stage invoices kept on the server (manifest entries with stage: true), so nobody fumbles a file picker on stage. */
export interface DemoInvoice {
  name: string // path under data/invoices/, e.g. poisoned/white_text_zh.pdf
  kind: 'clean' | 'poisoned'
  title_en: string
  title_zh: string
  note_en?: string
  note_zh?: string
}

export interface BatchSummary {
  total: number
  done: number
  paid: number
  refused: number
  blocked: number
  no_invoice: number
  false_alarms: number
}

export interface RateLimitError {
  message_en: string
  message_zh: string
}

// Public reputation schema: docs/REPUTATION.schema.json. No private invoice fields.
export interface AgentHistory {
  id: string
  chain_id: number
  contract_address: string
  agent_address: string
  label: "guarded" | "naive"
  role_en: string
  role_zh: string
  active: boolean
  status: "no_history" | "no_flag_observed" | "suspicious_observed"
  status_en: string
  status_zh: string
  first_observed_at: string | null
  last_observed_at: string | null
  counts: Counts
  breakdown: Array<Breakdown>
  recent_observations: Array<Observation>
}

export interface Breakdown {
  source: string
  scenario: string
  model_versions: Record<string, string>
  guard_version: string | null
  counts: Counts
}

export interface Counts {
  observations: number
  attempts: number
  refusals: number
  proposals: number
  known_attack_attempts: number
  known_attack_refusals: number
  suspicious_proposals: number
  confirmed_payments: number
  policy_blocks: number
  errors: number
  receipt_only: number
  unverified: number
}

export interface Coverage {
  network: string
  chain_id: number
  contract_address: string
  observed_from_block: number | null
  observed_to_block: number | null
  scan_from_block: number | null
  scanned_through_block: number | null
  last_sync: string | null
  stale: boolean
  gaps: Array<string>
  scope: "configured_vault_observed_history"
}

export interface Observation {
  id: string
  time: string
  source: "bounty" | "seed" | "team" | "batch" | "unknown"
  scenario: "known_attack" | "clean_fixture" | "unlabeled" | "unknown"
  model_versions: Record<string, string>
  guard_version: string | null
  outcome: "paid" | "blocked" | "refused" | "no_invoice" | "error" | "pending" | "unverified"
  reason_codes: Array<string>
  evidence: Array<"application_record" | "verified_transaction">
  transaction_url: string | null
  suspicious: boolean
  summary_en: string
  summary_zh: string
}

export interface ReputationView {
  agents: Array<AgentHistory>
  updated_at: string
  coverage: Coverage
}

export interface Health { ok: boolean; degraded_reasons: string[] }
