import { NavLink } from 'react-router-dom'
import {
  Activity,
  Bell,
  Compass,
  FlaskConical,
  LayoutDashboard,
  Upload,
  X,
} from 'lucide-react'

const links = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/explore', label: 'Explorer', icon: Compass },
  { to: '/research', label: 'Research', icon: FlaskConical },
  { to: '/alerts', label: 'Signals', icon: Bell },
  { to: '/upload', label: 'Ingest', icon: Upload },
]

interface SidebarProps {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`fixed md:sticky top-0 z-50 flex h-screen w-[232px] shrink-0 flex-col border-r transition-transform duration-200 ${
          open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
        style={{ borderColor: 'var(--line)', background: 'var(--ink-soft)' }}
      >
        <div className="flex items-center justify-between px-5 pb-5 pt-6">
          <NavLink to="/" className="flex items-center gap-2.5" onClick={onClose}>
            <span
              className="flex h-8 w-8 items-center justify-center rounded-lg"
              style={{ background: 'var(--lime)', color: '#0c1106' }}
            >
              <Activity size={17} strokeWidth={2.4} />
            </span>
            <span>
              <span className="display block text-[19px] leading-none">Signal</span>
              <span className="eyebrow mt-1 block text-[8px]">Sentiment intelligence</span>
            </span>
          </NavLink>
          <button
            onClick={onClose}
            className="text-[var(--muted)] md:hidden"
            aria-label="Close menu"
          >
            <X size={18} />
          </button>
        </div>

        <div className="mx-5 h-px" style={{ background: 'var(--line)' }} />

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-5">
          <p className="eyebrow px-3 pb-2 text-[8px]">Workspace</p>
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onClose}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition-all ${
                  isActive ? 'text-[#0b1005]' : 'text-[var(--muted)] hover:text-[var(--text)]'
                }`
              }
              style={({ isActive }) => ({
                background: isActive ? 'var(--lime)' : undefined,
              })}
            >
              <Icon size={15} strokeWidth={2} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="mx-4 mb-4 rounded-xl border p-3.5" style={{ borderColor: 'var(--line)' }}>
          <div className="mb-2 flex items-center gap-2">
            <span className="live-dot" />
            <span className="eyebrow text-[8px]">Corpus online</span>
          </div>
          <p className="text-[11px] leading-relaxed text-[var(--muted)]">
            1.65M public posts, model-scored. Research artifacts are versioned with the app.
          </p>
          <div className="mt-3 flex items-center justify-between text-[10px] text-[var(--muted-2)]">
            <span>v2.0</span>
            <span>CPU serving</span>
          </div>
        </div>
      </aside>
    </>
  )
}
