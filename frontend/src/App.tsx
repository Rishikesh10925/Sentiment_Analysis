import { Suspense, lazy, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { api } from './api/client'
import { useApi } from './api/useApi'
import { Sidebar } from './components/Sidebar'
import { LoadingState } from './components/States'
import { TopBar } from './components/TopBar'
import { Overview } from './pages/Overview'
import { FilterProvider } from './state/filters'

// Secondary routes are split out of the initial bundle; Overview (the landing
// page, and the heaviest chart consumer) stays eager so first paint is fast.
const ContentExplorer = lazy(() =>
  import('./pages/ContentExplorer').then((module) => ({ default: module.ContentExplorer })),
)
const Research = lazy(() =>
  import('./pages/Research').then((module) => ({ default: module.Research })),
)
const Alerts = lazy(() => import('./pages/Alerts').then((module) => ({ default: module.Alerts })))
const UploadPage = lazy(() =>
  import('./pages/UploadPage').then((module) => ({ default: module.UploadPage })),
)

export function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const meta = useApi(api.meta, [])

  return (
    <FilterProvider meta={meta.data}>
      <div className="flex min-h-screen">
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

        <div className="min-w-0 flex-1">
          <TopBar onMenu={() => setSidebarOpen(true)} />

          <main className="mx-auto w-full max-w-[1500px] px-4 py-5 sm:px-6 sm:py-7 lg:px-8">
            <Routes>
              <Route path="/" element={<Overview metaState={meta} />} />
              <Route
                path="/explore"
                element={
                  <Suspense fallback={<LoadingState label="Loading explorer" />}>
                    <ContentExplorer />
                  </Suspense>
                }
              />
              <Route
                path="/research"
                element={
                  <Suspense fallback={<LoadingState label="Loading research" />}>
                    <Research />
                  </Suspense>
                }
              />
              <Route
                path="/alerts"
                element={
                  <Suspense fallback={<LoadingState label="Loading alerts" />}>
                    <Alerts />
                  </Suspense>
                }
              />
              <Route
                path="/upload"
                element={
                  <Suspense fallback={<LoadingState label="Loading upload" />}>
                    <UploadPage />
                  </Suspense>
                }
              />

              {/* Backwards-compatible routes from the v1 dashboard. */}
              <Route path="/platforms" element={<Navigate to="/" replace />} />
              <Route path="/topics" element={<Navigate to="/" replace />} />
              <Route path="/explorer" element={<Navigate to="/explore" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>

            <footer
              className="mt-10 flex flex-wrap items-center justify-between gap-3 border-t pt-5 text-[10px] text-[var(--muted-2)]"
              style={{ borderColor: 'var(--line)' }}
            >
              <span>
                Signal · real public corpora · model predictions, not ground truth
              </span>
              <span className="mono">
                {meta.data?.provenance.generated_at?.slice(0, 10) ?? '2026'} · v2.0
              </span>
            </footer>
          </main>
        </div>
      </div>
    </FilterProvider>
  )
}
