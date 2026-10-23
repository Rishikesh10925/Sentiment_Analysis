import { AlertOctagon, BellRing, CalendarClock, ShieldCheck, TrendingDown } from 'lucide-react'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { ErrorState, LoadingState, Panel } from '../components/States'
import { useFilters } from '../state/filters'

export function Alerts() {
  const { filters } = useFilters()
  const alerts = useApi(api.alerts, [])
  const summary = useApi(() => api.summary(filters), [
    filters.start,
    filters.end,
    filters.platform,
    filters.topic,
  ])
  const topics = useApi(() => api.topics(filters, 8), [
    filters.start,
    filters.end,
    filters.platform,
  ])

  if (alerts.loading || summary.loading) return <LoadingState label="Loading signal monitor" />
  if (alerts.error) return <ErrorState message={alerts.error} onRetry={alerts.reload} />
  if (!alerts.data || !summary.data) return <ErrorState message="No alert state available." />

  const triggered = alerts.data.alerts.filter((alert) => alert.triggered)
  const current = alerts.data.alerts.find((alert) => alert.type === 'negative_threshold')
  const threshold = alerts.data.configured_threshold
  const negative = summary.data.percentages.Negative
  const riskTopics = [...(topics.data?.topics ?? [])]
    .filter((topic) => topic.total >= 500)
    .sort((a, b) => b.negative_rate - a.negative_rate)
    .slice(0, 6)

  return (
    <div className="space-y-4">
      <div>
        <p className="eyebrow">Operational layer</p>
        <h1 className="mt-1 text-[30px] leading-tight">Signal monitor</h1>
        <p className="mt-1 max-w-2xl text-[12.5px] leading-relaxed text-[var(--muted)]">
          Thresholds are evaluated against the current filter selection. These are descriptive alerts computed from
          model predictions, not a real-time incident feed.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[0.9fr_1.4fr]">
        <section className="panel relative overflow-hidden p-5">
          <div
            className="absolute -right-16 -top-16 h-48 w-48 rounded-full blur-3xl"
            style={{ background: triggered.length ? 'color-mix(in srgb, var(--coral) 16%, transparent)' : 'color-mix(in srgb, var(--lime) 12%, transparent)' }}
          />
          <div className="relative">
            <div className="flex items-center justify-between">
              <p className="eyebrow text-[8px]">Negative share</p>
              {triggered.length ? <AlertOctagon size={17} className="text-negative" /> : <ShieldCheck size={17} className="text-lime" />}
            </div>
            <p className="mono mt-4 text-[52px] leading-none" style={{ color: negative > threshold ? 'var(--negative)' : 'var(--lime)' }}>
              {negative.toFixed(1)}<span className="text-[0.4em]">%</span>
            </p>
            <div className="mt-4">
              <div className="flex justify-between text-[9.5px] text-[var(--muted)]">
                <span>0%</span><span>threshold {threshold}%</span><span>100%</span>
              </div>
              <div className="relative mt-1.5 h-2 overflow-hidden rounded-full" style={{ background: 'var(--line)' }}>
                <div
                  className="absolute inset-y-0 left-0 rounded-full"
                  style={{ width: `${Math.min(100, negative)}%`, background: negative > threshold ? 'var(--negative)' : 'var(--lime)' }}
                />
                <div className="absolute inset-y-0 w-px bg-white/40" style={{ left: `${threshold}%` }} />
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2 text-[10px]">
              <div className="panel-soft p-2.5">
                <p className="text-[var(--muted-2)]">Triggered</p>
                <p className="mono mt-1 text-[14px]">{triggered.length} / {alerts.data.alerts.length}</p>
              </div>
              <div className="panel-soft p-2.5">
                <p className="text-[var(--muted-2)]">Major topic</p>
                <p className="mt-1 text-[12px]">{current?.major_topic ?? '—'}</p>
              </div>
            </div>
            <p className="mt-3 text-[9.5px] leading-relaxed text-[var(--muted-2)]">
              Latest evaluation is stored with the database load. Re-run the loader after data changes.
            </p>
          </div>
        </section>

        <Panel title="Alert evaluations" eyebrow="Stored with this data version">
          <div className="divide-y" style={{ borderColor: 'var(--line-soft)' }}>
            {alerts.data.alerts.map((alert) => (
              <div key={alert.type} className="flex gap-3 px-4 py-4">
                <div
                  className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                  style={{
                    background: alert.triggered ? 'color-mix(in srgb, var(--coral) 12%, transparent)' : 'color-mix(in srgb, var(--lime) 10%, transparent)',
                    color: alert.triggered ? 'var(--negative)' : 'var(--lime)',
                  }}
                >
                  {alert.type === 'period_change' ? <TrendingDown size={15} /> : <BellRing size={15} />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-[12px] font-semibold">{alert.type.replace('_', ' ')}</p>
                    <span
                      className="rounded px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-wider"
                      style={{
                        color: alert.triggered ? 'var(--negative)' : 'var(--positive)',
                        background: alert.triggered ? 'color-mix(in srgb, var(--negative) 10%, transparent)' : 'color-mix(in srgb, var(--positive) 10%, transparent)',
                      }}
                    >
                      {alert.triggered ? 'triggered' : 'within range'}
                    </span>
                  </div>
                  <p className="mt-1.5 text-[11px] leading-relaxed text-[var(--muted)]">{alert.message}</p>
                  <p className="mono mt-2 flex flex-wrap items-center gap-3 text-[9px] text-[var(--muted-2)]">
                    <span className="inline-flex items-center gap-1"><CalendarClock size={10} /> threshold {alert.threshold ?? '—'}%</span>
                    <span>negative {alert.negative_percentage?.toFixed(2) ?? '—'}%</span>
                    <span>{alert.created_at?.replace('T', ' ').slice(0, 16)}</span>
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel title="Highest negative-share topics" eyebrow="Minimum 500 posts">
        <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
          {riskTopics.map((topic, index) => (
            <div key={topic.topic} className="panel-soft p-3.5">
              <div className="flex items-start justify-between">
                <div>
                  <span className="mono text-[9px] text-[var(--muted-2)]">{String(index + 1).padStart(2, '0')}</span>
                  <p className="mt-1 text-[12px] font-semibold">{topic.topic}</p>
                </div>
                <p className="mono text-[18px]" style={{ color: 'var(--negative)' }}>{topic.negative_rate.toFixed(1)}%</p>
              </div>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full" style={{ background: 'var(--line)' }}>
                <div className="h-full rounded-full" style={{ width: `${topic.negative_rate}%`, background: 'var(--negative)' }} />
              </div>
              <p className="mt-2 text-[9px] text-[var(--muted-2)]">
                {topic.total.toLocaleString()} posts · {topic.Negative.toLocaleString()} negative
              </p>
            </div>
          ))}
          {!riskTopics.length && <p className="text-[11px] text-[var(--muted)]">No topic has 500 posts in this slice.</p>}
        </div>
      </Panel>
    </div>
  )
}
