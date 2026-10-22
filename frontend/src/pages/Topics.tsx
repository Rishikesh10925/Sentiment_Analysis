import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { PLATFORM_COLORS, SENTIMENT_COLOR } from '../components/SentimentBadge'

function FrequencyChart<T extends Record<string, unknown>>({
  data,
  dataKeyLabel,
  dataKeyCount,
  color,
}: {
  data: T[]
  dataKeyLabel: Extract<keyof T, string>
  dataKeyCount: Extract<keyof T, string>
  color: string
}) {
  if (data.length === 0) return <EmptyState />
  return (
    <ResponsiveContainer width="100%" height={360}>
      <BarChart data={data} layout="vertical" margin={{ left: 12 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 12 }} />
        <YAxis type="category" dataKey={dataKeyLabel} width={110} tick={{ fontSize: 11 }} />
        <Tooltip />
        <Bar dataKey={dataKeyCount} fill={color} radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function Topics() {
  const topics = useApi(api.topics, [])
  const hashtags = useApi(() => api.hashtags(15), [])
  const keywords = useApi(() => api.keywords(15), [])

  if (topics.loading) return <LoadingState label="Loading topics..." />
  if (topics.error) return <ErrorState message={topics.error} onRetry={topics.reload} />
  if (!topics.data || topics.data.length === 0) return <EmptyState />

  const sorted = [...topics.data].sort((a, b) => b.total - a.total)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Topic Analysis</h1>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">Frequency and sentiment breakdown by topic.</p>
      </div>

      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <h2 className="text-sm font-semibold mb-4">Topic Frequency</h2>
        <ResponsiveContainer width="100%" height={420}>
          <BarChart data={sorted} layout="vertical" margin={{ left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 12 }} />
            <YAxis type="category" dataKey="topic" width={130} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="Positive" stackId="s" fill={SENTIMENT_COLOR.Positive} />
            <Bar dataKey="Neutral" stackId="s" fill={SENTIMENT_COLOR.Neutral} />
            <Bar dataKey="Negative" stackId="s" fill={SENTIMENT_COLOR.Negative} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <h2 className="text-sm font-semibold mb-4">Top Hashtags</h2>
          {hashtags.loading ? (
            <LoadingState />
          ) : hashtags.error ? (
            <ErrorState message={hashtags.error} onRetry={hashtags.reload} />
          ) : (
            <FrequencyChart
              data={(hashtags.data ?? []).map((h) => ({ ...h, hashtag: `#${h.hashtag}` }))}
              dataKeyLabel="hashtag"
              dataKeyCount="count"
              color={PLATFORM_COLORS[0]}
            />
          )}
        </div>

        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <h2 className="text-sm font-semibold mb-4">Top Keywords</h2>
          {keywords.loading ? (
            <LoadingState />
          ) : keywords.error ? (
            <ErrorState message={keywords.error} onRetry={keywords.reload} />
          ) : (
            <FrequencyChart
              data={keywords.data ?? []}
              dataKeyLabel="keyword"
              dataKeyCount="count"
              color={PLATFORM_COLORS[4]}
            />
          )}
        </div>
      </div>
    </div>
  )
}
