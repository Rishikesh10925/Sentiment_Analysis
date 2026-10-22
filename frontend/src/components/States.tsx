import { AlertTriangle, Inbox, Loader2, RefreshCw } from 'lucide-react'

export function LoadingState({ label = 'Loading...' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-[var(--color-text-muted)]">
      <Loader2 className="animate-spin" size={28} />
      <p className="text-sm">{label}</p>
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <AlertTriangle className="text-[var(--color-negative)]" size={28} />
      <p className="text-sm text-[var(--color-text)] max-w-sm">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 rounded-md border border-[var(--color-border)] px-3 py-1.5 text-sm hover:bg-[var(--color-bg)] transition-colors"
        >
          <RefreshCw size={14} /> Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ message = 'Nothing to show yet.' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-[var(--color-text-muted)]">
      <Inbox size={28} />
      <p className="text-sm">{message}</p>
    </div>
  )
}
