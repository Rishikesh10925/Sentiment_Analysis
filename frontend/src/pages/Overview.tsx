import { FileText, Layers, MessageCircle, ThumbsDown, ThumbsUp } from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { AlertBanner } from '../components/AlertBanner'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { StatCard } from '../components/StatCard'
import { SENTIMENT_COLOR } from '../components/SentimentBadge'

export function Overview() {
  const summary = useApi(api.summary, [])
  const sentiment = useApi(api.sentiment, [])
  const platforms = useApi(api.platforms, [])
  const trends = useApi(() => api.trends('week'), [])
  const alerts = useApi(api.alerts, [])

  if (summary.loading || sentiment.loading || platforms.loading || trends.loading) {
    return <LoadingState label="Loading overview..." />
  }
  if (summary.error) return <ErrorState message={summary.error} onRetry={summary.reload} />
  if (!summary.data) return <EmptyState />

  const s = summary.data

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Overview</h1>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          Sentiment across {s.num_platforms} platforms and {s.num_topics} topics.
        </p>
      </div>

      {alerts.data && <AlertBanner alerts={alerts.data} />}

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <StatCard label="Total Posts" value={s.total_posts.toLocaleString()} icon={FileText} />
        <StatCard label="Positive" value={`${s.positive_pct}%`} icon={ThumbsUp} accent="positive" sub={`${s.positive_count.toLocaleString()} posts`} />
        <StatCard label="Neutral" value={`${s.neutral_pct}%`} icon={MessageCircle} accent="neutral" sub={`${s.neutral_count.toLocaleString()} posts`} />
        <StatCard label="Negative" value={`${s.negative_pct}%`} icon={ThumbsDown} accent="negative" sub={`${s.negative_count.toLocaleString()} posts`} />
        <StatCard label="Platforms" value={s.num_platforms} icon={Layers} />
        <StatCard label="Topics" value={s.num_topics} icon={Layers} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <h2 className="text-sm font-semibold mb-4">Sentiment Distribution</h2>
          {sentiment.data && sentiment.data.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={sentiment.data}
                  dataKey="count"
                  nameKey="sentiment"
                  innerRadius={60}
                  outerRadius={95}
                  paddingAngle={2}
                >
                  {sentiment.data.map((row) => (
                    <Cell key={row.sentiment} fill={SENTIMENT_COLOR[row.sentiment]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value, _name, item) => [`${value} posts`, item.payload.sentiment]} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState />
          )}
        </div>

        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <h2 className="text-sm font-semibold mb-4">Platform Comparison</h2>
          {platforms.data && platforms.data.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={platforms.data} layout="vertical" margin={{ left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis type="category" dataKey="platform" width={90} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="Positive" stackId="s" fill={SENTIMENT_COLOR.Positive} radius={[0, 0, 0, 0]} />
                <Bar dataKey="Neutral" stackId="s" fill={SENTIMENT_COLOR.Neutral} />
                <Bar dataKey="Negative" stackId="s" fill={SENTIMENT_COLOR.Negative} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState />
          )}
        </div>
      </div>

      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <h2 className="text-sm font-semibold mb-4">Sentiment Trend (Weekly)</h2>
        {trends.data && trends.data.length > 0 ? (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={trends.data} margin={{ left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis
                dataKey="period"
                tick={{ fontSize: 11 }}
                tickFormatter={(v: string) => v.slice(0, 10)}
                minTickGap={20}
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip labelFormatter={(v) => (typeof v === 'string' ? v.slice(0, 10) : String(v))} />
              <Legend />
              <Line type="monotone" dataKey="positive" stroke={SENTIMENT_COLOR.Positive} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="neutral" stroke={SENTIMENT_COLOR.Neutral} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="negative" stroke={SENTIMENT_COLOR.Negative} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <EmptyState />
        )}
      </div>
    </div>
  )
}
