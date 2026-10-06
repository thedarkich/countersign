import { lazy, Suspense } from 'react'
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ServerBanner } from './components/ServerBanner'
import { isServerProblem, markServer } from './lib/net'
import { LangProvider } from './i18n'
import BountyPage from './pages/Bounty'

// The bounty page is what phones open from the QR code, so it ships in the main bundle.
// Everything else loads on demand; Controls carries wagmi and viem.
const LedgerPage = lazy(() => import('./pages/Ledger'))
const InboxPage = lazy(() => import('./pages/Inbox'))
const ControlsPage = lazy(() => import('./pages/Controls'))

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
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route path="/" element={<Navigate to="/bounty" replace />} />
              <Route path="/bounty" element={<BountyPage />} />
              <Route path="/ledger" element={<LedgerPage />} />
              <Route path="/inbox" element={<InboxPage />} />
              <Route path="/controls" element={<ControlsPage />} />
              <Route path="*" element={<Navigate to="/bounty" replace />} />
            </Routes>
          </Suspense>
        </HashRouter>
      </LangProvider>
    </QueryClientProvider>
  )
}
