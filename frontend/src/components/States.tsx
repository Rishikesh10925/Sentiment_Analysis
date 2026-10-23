import type { ReactNode } from 'react'
import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react'

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="space-y-4" aria-busy="true" aria-label={label}>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((item) => (
          <div key={item} className="panel h-28 animate-pulse p-4">
            <div className="h-2 w-20 rounded" style={{ background: 'var(--line)' }} />
            <div className="mt-4 h-7 w-28 rounded" style={{ background: 'var(--line)' }} />
          </div>
        ))}
      </div>
      <div className="panel h-80 animate-pulse" />
    </div>
  )
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string
  onRetry?: () => void
}) {
  return (
    <div className="panel flex flex-col items-center justify-center px-6 py-16 text-center">
      <AlertTriangle size={24} style={{ color: 'var(--coral)' }} />
      <p className="mt-3 text-sm font-semibold">The data could not be loaded</p>
      <p className="mt-1 max-w-md text-xs text-[var(--muted)]">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn mt-5">
          <RefreshCw size={13} /> Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ children }: { children?: ReactNode }) {
  return (
    <div className="panel flex flex-col items-center justify-center px-6 py-16 text-center">
      <Inbox size={24} className="text-[var(--muted)]" />
      <p className="mt-3 text-sm font-semibold">No posts match these filters</p>
      <p className="mt-1 text-xs text-[var(--muted)]">
        {children ?? 'Broaden the date range, platform or topic.'}
      </p>
    </div>
  )
}

export function Panel({
  children,
  className = '',
  title,
  eyebrow,
  action,
}: {
  children: ReactNode
  className?: string
  title?: string
  eyebrow?: string
  action?: ReactNode
}) {
  return (
    <section className={`panel overflow-hidden ${className}`}>
      {(title || action) && (
        <div className="flex items-start justify-between gap-3 border-b px-4 py-3.5 sm:px-5" style={{ borderColor: 'var(--line-soft)' }}>
          <div>
            {eyebrow && <p className="eyebrow text-[8px]">{eyebrow}</p>}
            {title && <h2 className="mt-0.5 text-[15px]">{title}</h2>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}
