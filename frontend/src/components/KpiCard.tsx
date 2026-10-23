import type { LucideIcon } from 'lucide-react'
import { ArrowDownRight, ArrowUpRight } from 'lucide-react'

export function KpiCard({
  label,
  value,
  sub,
  delta,
  accent = 'var(--text)',
  icon: Icon,
}: {
  label: string
  value: string | number
  sub?: string
  delta?: number | null
  accent?: string
  icon?: LucideIcon
}) {
  return (
    <div className="panel group relative overflow-hidden p-4 transition-colors hover:border-[color-mix(in_srgb,var(--lime)_28%,var(--line))]">
      <div
        className="absolute -right-8 -top-8 h-24 w-24 rounded-full opacity-[0.07] blur-2xl transition-opacity group-hover:opacity-[0.14]"
        style={{ background: accent }}
      />
      <div className="flex items-center justify-between">
        <p className="eyebrow text-[8px]">{label}</p>
        {Icon && <Icon size={14} style={{ color: accent }} strokeWidth={1.8} />}
      </div>
      <p className="mono mt-3 text-[26px] font-medium leading-none tracking-tight" style={{ color: accent }}>
        {value}
      </p>
      <div className="mt-2 flex items-center gap-2 text-[10.5px] text-[var(--muted)]">
        {delta != null && (
          <span
            className="inline-flex items-center gap-0.5 font-semibold"
            style={{ color: delta >= 0 ? 'var(--positive)' : 'var(--negative)' }}
          >
            {delta >= 0 ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}
            {Math.abs(delta).toFixed(2)} pp
          </span>
        )}
        {sub && <span className="truncate">{sub}</span>}
      </div>
    </div>
  )
}
