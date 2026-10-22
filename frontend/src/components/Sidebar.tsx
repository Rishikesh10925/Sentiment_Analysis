import { NavLink } from 'react-router-dom'
import { AlertOctagon, LayoutDashboard, MessageSquareText, Share2, Tags, Upload, X } from 'lucide-react'

const links = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/platforms', label: 'Platform Analysis', icon: Share2 },
  { to: '/topics', label: 'Topic Analysis', icon: Tags },
  { to: '/explorer', label: 'Content Explorer', icon: MessageSquareText },
  { to: '/alerts', label: 'Alerts', icon: AlertOctagon },
  { to: '/upload', label: 'Upload Data', icon: Upload },
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
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`w-60 shrink-0 border-r border-[var(--color-border)] bg-[var(--color-surface)] h-screen fixed md:sticky top-0 flex flex-col z-40 transition-transform duration-200 ${
          open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <div className="px-5 py-5 border-b border-[var(--color-border)] flex items-center justify-between">
          <div>
            <p className="font-semibold text-sm leading-tight">Sentiment &amp; Trend</p>
            <p className="text-xs text-[var(--color-text-muted)] leading-tight mt-0.5">Multi-Platform Analytics</p>
          </div>
          <button onClick={onClose} className="md:hidden text-[var(--color-text-muted)]" aria-label="Close menu">
            <X size={18} />
          </button>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-indigo-600 text-white'
                    : 'text-[var(--color-text-muted)] hover:bg-[var(--color-bg)] hover:text-[var(--color-text)]'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-4 border-t border-[var(--color-border)] text-xs text-[var(--color-text-muted)]">
          Synthetic demo data
        </div>
      </aside>
    </>
  )
}
