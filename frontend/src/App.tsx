import { useState } from 'react'
import { Menu } from 'lucide-react'
import { Route, Routes } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { Overview } from './pages/Overview'
import { Platforms } from './pages/Platforms'
import { Topics } from './pages/Topics'
import { ContentExplorer } from './pages/ContentExplorer'
import { Alerts } from './pages/Alerts'
import { UploadPage } from './pages/UploadPage'

export function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex-1 min-w-0">
        <header className="md:hidden sticky top-0 z-20 flex items-center gap-3 border-b border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
            className="text-[var(--color-text-muted)]"
          >
            <Menu size={20} />
          </button>
          <p className="font-semibold text-sm">Sentiment &amp; Trend</p>
        </header>

        <main className="p-4 sm:p-6 lg:p-8 max-w-full overflow-x-hidden">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/platforms" element={<Platforms />} />
            <Route path="/topics" element={<Topics />} />
            <Route path="/explorer" element={<ContentExplorer />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/upload" element={<UploadPage />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
