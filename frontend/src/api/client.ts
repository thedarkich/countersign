import type {
  Health,
  ReputationView,
  AgentKind,
  AppConfig,
  Attempt,
  BatchSummary,
  ChangeKind,
  EvalResults,
  LeaderboardEntry,
  DemoInvoice,
  LedgerEvent,
  LedgerKind,
  Registry,
  Source,
  Stats,
} from './types'
import { getDeviceId } from '../lib/device'
import { mockApi } from './mock'

export interface SubmitInput {
  nickname: string
  address?: string
  agent: AgentKind
  text?: string
  file?: File | null
  demo?: string // a stage invoice on the server (its manifest name), instead of a file
}

export class RateLimitedError extends Error {
  constructor(
    public message_en: string,
    public message_zh: string,
  ) {
    super(message_en)
  }
}

export class AuthError extends Error {}

/** Owner actions. Live mode sends these through the wallet (see pages/Controls); mock mode simulates them. */
export interface MockOwner {
  queue(kind: ChangeKind, decoded: Record<string, string | number>): Promise<void>
  execute(id: string): Promise<void>
  cancel(id: string): Promise<void>
  pause(): Promise<void>
  deactivateVendor(id: number): Promise<void>
  closePO(id: number): Promise<void>
  revokeAgent(address: string): Promise<void>
  lowerDailyCap(cap: string): Promise<void>
}

export interface Api {
  mode: 'live' | 'mock'
  health(): Promise<Health>
  reputation(): Promise<ReputationView>
  config(): Promise<AppConfig>
  stats(): Promise<Stats>
  leaderboard(): Promise<LeaderboardEntry[]>
  ledger(kind: LedgerKind, limit?: number): Promise<LedgerEvent[]>
  registry(): Promise<Registry>
  evalResults(): Promise<EvalResults>
  attempt(id: string): Promise<Attempt>
  submitBounty(input: SubmitInput): Promise<{ attempt_id: string }>
  teamAttempts(source?: Source | 'all', limit?: number): Promise<Attempt[]>
  submitTeam(input: SubmitInput): Promise<{ attempt_id: string }>
  demoInvoices(): Promise<DemoInvoice[]>
  runBatch(): Promise<{ batch_id: string }>
  batch(id: string): Promise<BatchSummary>
  ownerTx(txHash: string): Promise<unknown>
  mockOwner?: MockOwner
}

const ADMIN_KEY = 'cs_admin_token'
let memoryToken: string | null = null
export function getAdminToken(): string | null {
  try {
    return localStorage.getItem(ADMIN_KEY) ?? memoryToken
  } catch {
    return memoryToken
  }
}
export function setAdminToken(token: string) {
  try {
    localStorage.setItem(ADMIN_KEY, token)
  } catch {
    /* storage unavailable: token lives for this page only */
  }
  memoryToken = token
}
export function clearAdminToken() {
  try {
    localStorage.removeItem(ADMIN_KEY)
  } catch {
    /* ignore */
  }
  memoryToken = null
}

async function request<T>(path: string, init: RequestInit = {}, admin = false): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('X-Device-Id', getDeviceId())
  if (admin) {
    const token = getAdminToken()
    if (token) headers.set('Authorization', `Bearer ${token}`)
  }
  const res = await fetch(path, { ...init, headers })
  if (res.status === 429) {
    const body = await res.json().catch(() => ({}))
    throw new RateLimitedError(
      body.message_en ?? 'Too many attempts. Wait a minute and try again.',
      body.message_zh ?? '提交太频繁了，请等一分钟再试。',
    )
  }
  if (res.status === 401 || res.status === 403) throw new AuthError('Admin token rejected')
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} on ${path}`)
  return res.json() as Promise<T>
}

function form(input: SubmitInput): FormData {
  const fd = new FormData()
  fd.set('nickname', input.nickname)
  if (input.address) fd.set('address', input.address)
  fd.set('agent', input.agent)
  if (input.text) fd.set('text', input.text)
  if (input.file) fd.set('file', input.file)
  if (input.demo) fd.set('demo', input.demo)
  return fd
}

const liveApi: Api = {
  mode: 'live',
  health: () => request('/api/health'),
  reputation: () => request('/api/reputation'),
  config: () => request('/api/config'),
  stats: () => request('/api/stats'),
  leaderboard: () => request('/api/leaderboard'),
  ledger: (kind, limit = 100) => request(`/api/ledger?kind=${kind}&limit=${limit}`),
  registry: () => request('/api/registry'),
  evalResults: () => request('/api/eval'),
  attempt: (id) => request(`/api/attempts/${encodeURIComponent(id)}`, {}, true),
  submitBounty: (input) => request('/api/bounty/attempts', { method: 'POST', body: form(input) }),
  teamAttempts: (source = 'all', limit = 100) =>
    request(`/api/team/attempts?limit=${limit}${source === 'all' ? '' : `&source=${source}`}`, {}, true),
  submitTeam: (input) => request('/api/team/attempts', { method: 'POST', body: form(input) }, true),
  demoInvoices: () => request('/api/team/demo-invoices', {}, true),
  runBatch: () =>
    request(
      '/api/team/batch',
      { method: 'POST', body: JSON.stringify({ folder: 'clean' }), headers: { 'Content-Type': 'application/json' } },
      true,
    ),
  batch: (id) => request(`/api/team/batch/${encodeURIComponent(id)}`, {}, true),
  ownerTx: (txHash) =>
    request(
      '/api/team/owner-tx',
      { method: 'POST', body: JSON.stringify({ tx_hash: txHash }), headers: { 'Content-Type': 'application/json' } },
      true,
    ),
}

export const api: Api = import.meta.env.VITE_API_MODE === 'mock' ? mockApi : liveApi
