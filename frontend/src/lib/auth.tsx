import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, clearAdminToken } from '../api/client'
import { useLang } from '../i18n'
import { getDeviceId } from './device'

export interface User { id: string; name: string; email: string }
type AuthResult = { response: { ok: boolean; status: number }; result: { user?: User } }
type Auth = {
  user: User | null; loading: boolean; error: string
  refresh: () => Promise<void>; signedIn: (user: User) => void; logout: () => Promise<void>
}
const AuthContext = createContext<Auth | null>(null)
const MOCK_KEY = 'cs_mock_user'

/** Account endpoints use the HttpOnly session cookie. Mock builds simulate them so the flow can be rehearsed offline. */
export async function authRequest(path: string, data?: Record<string, string>): Promise<AuthResult> {
  if (api.mode === 'mock') return mockAuth(path, data)
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 12_000)
  try {
    const response = await fetch(path, {
      method: data === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: { 'X-Device-Id': getDeviceId(), ...(data === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: data === undefined ? undefined : JSON.stringify(data), signal: controller.signal,
    })
    return { response, result: await response.json().catch(() => ({})) }
  } finally { clearTimeout(timer) }
}

function mockAuth(path: string, data?: Record<string, string>): AuthResult {
  const ok = (user?: User): AuthResult => ({ response: { ok: true, status: 200 }, result: { user } })
  try {
    if (path === '/api/me') {
      const user = JSON.parse(sessionStorage.getItem(MOCK_KEY) ?? 'null') as User | null
      return user ? ok(user) : { response: { ok: false, status: 401 }, result: {} }
    }
    if (path === '/api/logout') { sessionStorage.removeItem(MOCK_KEY); return ok() }
    const user = { id: 'mock-user', name: data?.name || 'Mock member', email: (data?.email ?? '').toLowerCase() }
    sessionStorage.setItem(MOCK_KEY, JSON.stringify(user))
    return ok(user)
  } catch {
    return ok({ id: 'mock-user', name: data?.name || 'Mock member', email: (data?.email ?? '').toLowerCase() })
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const { tr } = useLang()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [problem, setProblem] = useState<'' | 'unavailable' | 'unreachable'>('')
  const qc = useQueryClient()
  const revision = useRef(0)
  const signedInRef = useRef(false)
  const setAccount = useCallback((next: User | null) => {
    revision.current++
    signedInRef.current = !!next
    void qc.cancelQueries()
    qc.clear()  // nothing private from the previous account stays cached
    setUser(next)
    setProblem('')
    setLoading(false)
  }, [qc])
  const refresh = useCallback(async () => {
    const current = revision.current
    try {
      const { response, result } = await authRequest('/api/me')
      if (revision.current !== current) return
      if (response.ok && result.user) { signedInRef.current = true; setUser(result.user); setProblem('') }
      else if (response.status === 401) { if (signedInRef.current) setAccount(null); else { setUser(null); setProblem('') } }
      else setProblem('unavailable')
    } catch {
      if (revision.current === current) setProblem('unreachable')
    } finally { if (revision.current === current) setLoading(false) }
  }, [setAccount])
  useEffect(() => {
    void refresh()
    const interval = setInterval(() => { if (document.visibilityState === 'visible') void refresh() }, 60_000)
    const visible = () => { if (document.visibilityState === 'visible') void refresh() }
    document.addEventListener('visibilitychange', visible)
    return () => { clearInterval(interval); document.removeEventListener('visibilitychange', visible) }
  }, [refresh])
  const logout = async () => {
    const { response } = await authRequest('/api/logout', {})
    if (!response.ok) throw new Error('logout failed')
    clearAdminToken()
    setAccount(null)
  }
  const error = problem === 'unavailable' ? tr('The sign-in service is unavailable. Try again shortly.', '登录服务暂不可用，请稍后重试。')
    : problem === 'unreachable' ? tr("Can't reach the sign-in service. Try again shortly.", '无法连接登录服务，请稍后重试。') : ''
  return <AuthContext.Provider value={{ user, loading, error, refresh, signedIn: setAccount, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}

/** Only workspace routes are valid post-sign-in destinations. */
export function workspaceDestination(value: string | null) {
  if (!value) return '/inbox'
  return /^\/(inbox|ledger|controls|bounty)(?:\?[^#]*)?$/.test(value) ? value : '/inbox'
}
