import { AlertTriangle, CheckCircle2 } from 'lucide-react'
import type { AlertsResponse } from '../types'

/** Compact alert banner retained for compatibility with embedded views. */
export function AlertBanner({ alerts }: { alerts: AlertsResponse }) {
  const triggered = alerts.alerts.filter((alert) => alert.triggered)

  if (triggered.length === 0) {
    return (
      <div className="flex items-center gap-2.5 rounded-lg border px-4 py-3 text-[12px]" style={{ borderColor: 'var(--line)', color: 'var(--positive)' }}>
        <CheckCircle2 size={16} className="shrink-0" />
        <span>No active alerts. Sentiment is within configured thresholds.</span>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {triggered.map((alert) => (
        <div
          key={alert.type}
          className="flex items-start gap-2.5 rounded-lg border px-4 py-3 text-[12px]"
          style={{ borderColor: 'color-mix(in srgb, var(--negative) 30%, var(--line))', color: 'var(--negative)' }}
        >
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <span>{alert.message}</span>
        </div>
      ))}
    </div>
  )
}
