import { useState } from 'react'
import { Search } from 'lucide-react'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { SentimentBadge } from '../components/SentimentBadge'
import type { Sentiment } from '../types'

const PLATFORMS = ['Instagram', 'Facebook', 'YouTube', 'Reddit', 'X/Twitter', 'WhatsApp Export']
const SENTIMENTS: Sentiment[] = ['Positive', 'Neutral', 'Negative']
const PAGE_SIZE = 15

export function ContentExplorer() {
  const [platform, setPlatform] = useState('')
  const [sentiment, setSentiment] = useState('')
  const [topic, setTopic] = useState('')
  const [date, setDate] = useState('')
  const [keyword, setKeyword] = useState('')
  const [keywordInput, setKeywordInput] = useState('')
  const [page, setPage] = useState(0)

  const posts = useApi(
    () => api.posts({ platform, sentiment, topic, date, keyword, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    [platform, sentiment, topic, date, keyword, page],
  )

  function resetFiltersAnd(fn: () => void) {
    setPage(0)
    fn()
  }

  const totalPages = posts.data ? Math.ceil(posts.data.total / PAGE_SIZE) : 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Content Explorer</h1>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">Search and filter individual posts.</p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          resetFiltersAnd(() => setKeyword(keywordInput))
        }}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4"
      >
        <select
          value={platform}
          onChange={(e) => resetFiltersAnd(() => setPlatform(e.target.value))}
          className="rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm"
        >
          <option value="">All Platforms</option>
          {PLATFORMS.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>

        <select
          value={sentiment}
          onChange={(e) => resetFiltersAnd(() => setSentiment(e.target.value))}
          className="rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm"
        >
          <option value="">All Sentiments</option>
          {SENTIMENTS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <input
          type="text"
          placeholder="Topic (exact)"
          value={topic}
          onChange={(e) => resetFiltersAnd(() => setTopic(e.target.value))}
          className="rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm"
        />

        <input
          type="date"
          value={date}
          onChange={(e) => resetFiltersAnd(() => setDate(e.target.value))}
          className="rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm"
        />

        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Keyword..."
            value={keywordInput}
            onChange={(e) => setKeywordInput(e.target.value)}
            className="flex-1 rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm min-w-0"
          />
          <button
            type="submit"
            className="shrink-0 rounded-md bg-indigo-600 text-white px-3 py-2 text-sm font-medium hover:bg-indigo-700 transition-colors flex items-center gap-1.5"
          >
            <Search size={14} /> Search
          </button>
        </div>
      </form>

      {posts.loading ? (
        <LoadingState label="Searching posts..." />
      ) : posts.error ? (
        <ErrorState message={posts.error} onRetry={posts.reload} />
      ) : !posts.data || posts.data.items.length === 0 ? (
        <EmptyState message="No posts match these filters." />
      ) : (
        <>
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[var(--color-bg)] text-[var(--color-text-muted)] text-xs uppercase tracking-wide">
                <tr>
                  <th className="text-left font-medium px-4 py-3">Post</th>
                  <th className="text-left font-medium px-4 py-3">Platform</th>
                  <th className="text-left font-medium px-4 py-3">Topic</th>
                  <th className="text-left font-medium px-4 py-3">Date</th>
                  <th className="text-left font-medium px-4 py-3">Sentiment</th>
                </tr>
              </thead>
              <tbody>
                {posts.data.items.map((post) => (
                  <tr key={post.post_id} className="border-t border-[var(--color-border)] align-top">
                    <td className="px-4 py-3 max-w-md">
                      <p className="line-clamp-2">{post.original_text}</p>
                      {post.hashtags && (
                        <p className="text-xs text-indigo-500 mt-1 truncate">{post.hashtags}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">{post.platform}</td>
                    <td className="px-4 py-3 whitespace-nowrap">{post.topic}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-[var(--color-text-muted)]">
                      {post.date?.slice(0, 10) ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <SentimentBadge sentiment={post.sentiment} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between text-sm text-[var(--color-text-muted)]">
            <span>
              {posts.data.total.toLocaleString()} result{posts.data.total === 1 ? '' : 's'} · page {page + 1} of{' '}
              {Math.max(totalPages, 1)}
            </span>
            <div className="flex gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                className="rounded-md border border-[var(--color-border)] px-3 py-1.5 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[var(--color-bg)] transition-colors"
              >
                Previous
              </button>
              <button
                disabled={page + 1 >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-md border border-[var(--color-border)] px-3 py-1.5 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[var(--color-bg)] transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
