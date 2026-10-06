import { useSyncExternalStore } from 'react'
import { AuthError, RateLimitedError } from '../api/client'

// One flag for "the backend isn't answering", set from React Query's cache callbacks.
let down = false
const subs = new Set<() => void>()

export function markServer(ok: boolean) {
  if (down === !ok) return
  down = !ok
  subs.forEach((f) => f())
}

/** Network failures and 5xx count; a rejected token or a rate limit means the server is fine. */
export function isServerProblem(err: unknown): boolean {
  if (err instanceof AuthError || err instanceof RateLimitedError) return false
  if (err instanceof TypeError) return true // fetch could not connect
  return err instanceof Error && /^5\d\d\b/.test(err.message)
}

export function useServerDown(): boolean {
  return useSyncExternalStore(
    (f) => {
      subs.add(f)
      return () => subs.delete(f)
    },
    () => down,
  )
}
