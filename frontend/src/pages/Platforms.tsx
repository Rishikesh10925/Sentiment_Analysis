import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { SENTIMENT_COLOR } from '../components/SentimentBadge'

export function Platforms() {
  const platforms = useApi(api.platforms, [])

  if (platforms.loading) return <LoadingState label="Loading platform data..." />
  if (platforms.error) return <ErrorState message={platforms.error} onRetry={platforms.reload} />
  if (!platforms.data || platforms.data.length === 0) return <EmptyState />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Platform Analysis</h1>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          Comparing sentiment across Instagram, Facebook, YouTube, Reddit, X/Twitter, and WhatsApp Export.
        </p>
      </div>

      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <h2 className="text-sm font-semibold mb-4">Post Volume &amp; Sentiment by Platform</h2>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={platforms.data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey="platform" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="Positive" stackId="s" fill={SENTIMENT_COLOR.Positive} />
            <Bar dataKey="Neutral" stackId="s" fill={SENTIMENT_COLOR.Neutral} />
            <Bar dataKey="Negative" stackId="s" fill={SENTIMENT_COLOR.Negative} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--color-bg)] text-[var(--color-text-muted)] text-xs uppercase tracking-wide">
            <tr>
              <th className="text-left font-medium px-4 py-3">Platform</th>
              <th className="text-right font-medium px-4 py-3">Total Posts</th>
              <th className="text-right font-medium px-4 py-3">Positive %</th>
              <th className="text-right font-medium px-4 py-3">Neutral %</th>
              <th className="text-right font-medium px-4 py-3">Negative %</th>
            </tr>
          </thead>
          <tbody>
            {platforms.data.map((row) => (
              <tr key={row.platform} className="border-t border-[var(--color-border)]">
                <td className="px-4 py-3 font-medium">{row.platform}</td>
                <td className="px-4 py-3 text-right tabular-nums">{row.total.toLocaleString()}</td>
                <td className="px-4 py-3 text-right tabular-nums text-[var(--color-positive)]">{row.positive_pct}%</td>
                <td className="px-4 py-3 text-right tabular-nums text-[var(--color-neutral)]">{row.neutral_pct}%</td>
                <td className="px-4 py-3 text-right tabular-nums text-[var(--color-negative)]">{row.negative_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
