import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  label: string
  value: string | number
  icon: LucideIcon
  accent?: 'positive' | 'neutral' | 'negative' | 'default'
  sub?: string
}

const accentStyles: Record<string, string> = {
  positive: 'text-[var(--color-positive)] bg-[var(--color-positive-bg)]',
  neutral: 'text-[var(--color-neutral)] bg-[var(--color-neutral-bg)]',
  negative: 'text-[var(--color-negative)] bg-[var(--color-negative-bg)]',
  default: 'text-indigo-600 bg-indigo-100 dark:bg-indigo-950 dark:text-indigo-300',
}

export function StatCard({ label, value, icon: Icon, accent = 'default', sub }: StatCardProps) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wide truncate">{label}</p>
        <p className="text-2xl font-semibold mt-1 tabular-nums">{value}</p>
        {sub && <p className="text-xs text-[var(--color-text-muted)] mt-1">{sub}</p>}
      </div>
      <div className={`rounded-lg p-2.5 shrink-0 ${accentStyles[accent]}`}>
        <Icon size={18} />
      </div>
    </div>
  )
}
