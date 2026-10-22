import { AlertTriangle, CheckCircle2 } from 'lucide-react'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { SentimentBadge } from '../components/SentimentBadge'

export function Alerts() {
  const alerts = useApi(api.alerts, [])
  const negativePosts = useApi(() => api.negativePosts(15), [])
  const topics = useApi(api.topics, [])

  if (alerts.loading) return <LoadingState label="Checking alerts..." />
  if (alerts.error) return <ErrorState message={alerts.error} onRetry={alerts.reload} />
  if (!alerts.data) return <EmptyState />

  const majorComplaintTopics = [...(topics.data ?? [])]
    .sort((a, b) => b.Negative - a.Negative)
    .slice(0, 8)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Alerts</h1>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          Negative sentiment threshold and trend alerts, plus the biggest sources of complaints.
        </p>
      </div>

      <div className="space-y-3">
        {alerts.data.map((alert) => (
          <div
            key={alert.type}
            className={`rounded-xl border p-4 flex items-start gap-3 ${
              alert.triggered
                ? 'border-[var(--color-negative)]/30 bg-[var(--color-negative-bg)]'
                : 'border-[var(--color-border)] bg-[var(--color-surface)]'
            }`}
          >
            {alert.triggered ? (
              <AlertTriangle size={20} className="text-[var(--color-negative)] shrink-0 mt-0.5" />
            ) : (
              <CheckCircle2 size={20} className="text-[var(--color-positive)] shrink-0 mt-0.5" />
            )}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">
                {alert.type === 'negative_threshold' ? 'Negative Sentiment Threshold' : 'Period-over-Period Change'}
              </p>
              {alert.triggered ? (
                <pre className="whitespace-pre-wrap font-sans text-sm text-[var(--color-negative)] mt-1">
                  {alert.message}
                </pre>
              ) : (
                <p className="text-sm text-[var(--color-text-muted)] mt-1">
                  {alert.type === 'negative_threshold'
                    ? `No alert — negative sentiment is ${alert.negative_percentage}%, below the ${alert.threshold}% threshold.`
                    : 'No significant swing in negative sentiment between the two most recent periods.'}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <h2 className="text-sm font-semibold mb-3">Major Complaint Topics</h2>
          {topics.loading ? (
            <LoadingState />
          ) : majorComplaintTopics.length === 0 ? (
            <EmptyState />
          ) : (
            <ul className="space-y-2">
              {majorComplaintTopics.map((t) => (
                <li key={t.topic} className="flex items-center justify-between text-sm">
                  <span className="truncate">{t.topic}</span>
                  <span className="text-[var(--color-negative)] font-medium tabular-nums shrink-0 ml-2">
                    {t.Negative} negative
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <h2 className="text-sm font-semibold mb-3">Most Negative Posts</h2>
          {negativePosts.loading ? (
            <LoadingState />
          ) : negativePosts.error ? (
            <ErrorState message={negativePosts.error} onRetry={negativePosts.reload} />
          ) : !negativePosts.data || negativePosts.data.length === 0 ? (
            <EmptyState message="No negative posts found." />
          ) : (
            <ul className="space-y-3 max-h-96 overflow-y-auto pr-1">
              {negativePosts.data.map((post) => (
                <li key={post.post_id} className="border-b border-[var(--color-border)] last:border-0 pb-3 last:pb-0">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-xs text-[var(--color-text-muted)]">
                      {post.platform} · {post.topic}
                    </span>
                    <SentimentBadge sentiment={post.sentiment} />
                  </div>
                  <p className="text-sm line-clamp-2">{post.original_text}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
