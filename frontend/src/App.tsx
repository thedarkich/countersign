import { lazy, Suspense } from 'react'
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ServerBanner } from './components/ServerBanner'
import { isServerProblem, markServer } from './lib/net'
import { AuthProvider } from './lib/auth'
import { LangProvider } from './i18n'
import BountyPage from './pages/Bounty'

// The bounty page is what phones open from the QR code, so it ships in the main bundle.
// Everything else loads on demand; Controls carries wagmi and viem.
const LandingPage = lazy(() => import('./pages/Landing'))
const AuthPage = lazy(() => import('./pages/Auth'))
const TeamAccess = lazy(() => import('./pages/TeamAccess'))
const LedgerPage = lazy(() => import('./pages/Ledger'))
const InboxPage = lazy(() => import('./pages/Inbox'))
const ControlsPage = lazy(() => import('./pages/Controls'))
const WalletPage = lazy(() => import('./pages/Wallet'))

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (err) => isServerProblem(err) && markServer(false),
    onSuccess: () => markServer(true),
  }),
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 1000 },
  },
})

function Loading() {
  return <div className="mx-auto mt-24 h-2 w-40 animate-pulse rounded-full bg-paper2" aria-label="Loading" />
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <LangProvider>
        <ServerBanner />
        {/* hash routes: the server never needs an SPA fallback, and links survive WeChat's in-app browser */}
        <HashRouter>
          <AuthProvider>
            <Suspense fallback={<Loading />}>
              <Routes>
                <Route path="/" element={<LandingPage />} />
                <Route path="/login" element={<AuthPage />} />
                <Route path="/signup" element={<AuthPage register />} />
                <Route path="/team-token" element={<TeamAccess />} />
                <Route path="/bounty" element={<BountyPage />} />
                <Route path="/ledger" element={<LedgerPage />} />
                <Route path="/inbox" element={<InboxPage />} />
                <Route path="/controls" element={<ControlsPage />} />
                <Route path="/wallet" element={<WalletPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </AuthProvider>
        </HashRouter>
      </LangProvider>
    </QueryClientProvider>
  )
}
