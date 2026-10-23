import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  Download,
  MessageSquareQuote,
  Search,
  Send,
  Sparkles,
  X,
} from 'lucide-react'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { SentimentBadge, SENTIMENT_COLOR } from '../components/SentimentBadge'
import { EmptyState, ErrorState, LoadingState, Panel } from '../components/States'
import { useFilters } from '../state/filters'
import type { PostDetail, PredictResponse, Sentiment } from '../types'

const PAGE_SIZE = 20
const LABELS: Sentiment[] = ['Negative', 'Neutral', 'Positive']

function ProbabilityBars({ probabilities }: { probabilities: Record<Sentiment, number | null> }) {
  return (
    <div className="space-y-2">
      {LABELS.map((label) => {
        const value = probabilities[label] ?? 0
        return (
          <div key={label}>
            <div className="flex justify-between text-[10px]">
              <span>{label}</span>
              <span className="mono">{(value * 100).toFixed(1)}%</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full" style={{ background: 'var(--line)' }}>
              <div
                className="h-full rounded-full"
                style={{ width: `${value * 100}%`, background: SENTIMENT_COLOR[label] }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function ContentExplorer() {
  const { filters } = useFilters()
  const [sentiment, setSentiment] = useState('')
  const [keyword, setKeyword] = useState('')
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState('date_desc')
  const [page, setPage] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<PostDetail | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [labText, setLabText] = useState('The update fixed the crashes, but battery life is still disappointing.')
  const [prediction, setPrediction] = useState<PredictResponse | null>(null)
  const [predicting, setPredicting] = useState(false)
  const [predictError, setPredictError] = useState<string | null>(null)

  const posts = useApi(
    () =>
      api.posts({
        ...filters,
        sentiment,
        keyword,
        sort,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    [filters.start, filters.end, filters.platform, filters.topic, sentiment, keyword, sort, page],
  )

  useEffect(() => {
    setPage(0)
  }, [sentiment, keyword, sort, filters.start, filters.end, filters.platform, filters.topic])

  useEffect(() => {
    if (!selectedId) return
    let cancelled = false
    setDetail(null)
    setDetailError(null)
    api
      .post(selectedId)
      .then((payload) => {
        if (!cancelled) setDetail(payload)
      })
      .catch((error: Error) => {
        if (!cancelled) setDetailError(error.message)
      })
    return () => {
      cancelled = true
    }
  }, [selectedId])

  async function runPrediction() {
    if (!labText.trim()) return
    setPredicting(true)
    setPredictError(null)
    try {
      setPrediction(await api.predict(labText))
    } catch (error) {
      setPredictError(error instanceof Error ? error.message : 'Prediction failed')
    } finally {
      setPredicting(false)
    }
  }

  const totalPages = posts.data ? Math.max(1, Math.ceil(posts.data.total / PAGE_SIZE)) : 1

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Evidence layer</p>
          <h1 className="mt-1 text-[30px] leading-tight">Content explorer</h1>
          <p className="mt-1 text-[12.5px] text-[var(--muted)]">
            Every row is a model prediction. Open any post to inspect its probabilities and token-level attribution.
          </p>
        </div>
        <a className="btn" href={api.postsExportUrl({ ...filters, sentiment, keyword })}>
          <Download size={13} /> Export filtered CSV
        </a>
      </div>

      <Panel title="Try the served model" eyebrow="Live inference · no row written">
        <div className="grid gap-4 p-4 lg:grid-cols-[1.2fr_0.8fr]">
          <div>
            <textarea
              className="field min-h-[104px] w-full resize-y leading-relaxed"
              value={labText}
              maxLength={2000}
              onChange={(event) => setLabText(event.target.value)}
              placeholder="Paste a short social post…"
            />
            <div className="mt-2 flex items-center justify-between gap-3">
              <span className="mono text-[9.5px] text-[var(--muted-2)]">{labText.length} / 2000</span>
              <button className="btn btn-primary" onClick={runPrediction} disabled={predicting || !labText.trim()}>
                <Send size={13} /> {predicting ? 'Scoring…' : 'Analyse text'}
              </button>
            </div>
            {predictError && <p className="mt-2 text-[11px] text-negative">{predictError}</p>}
          </div>

          <div className="panel-soft p-3.5">
            {prediction ? (
              <div>
                <div className="flex items-center justify-between">
                  <SentimentBadge sentiment={prediction.sentiment} score={prediction.confidence} />
                  <span className="eyebrow text-[7px]">{prediction.model.name}</span>
                </div>
                <div className="mt-3">
                  <ProbabilityBars probabilities={prediction.probabilities} />
                </div>
                <p className="mt-3 eyebrow text-[7px]">Strongest attributions</p>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {prediction.explanation.tokens.slice(0, 7).map((token) => (
                    <span
                      key={token.token}
                      className="rounded px-1.5 py-0.5 text-[10px]"
                      style={{
                        color: token.weight >= 0 ? 'var(--positive)' : 'var(--negative)',
                        background: `color-mix(in srgb, ${token.weight >= 0 ? 'var(--positive)' : 'var(--negative)'} 9%, transparent)`,
                      }}
                    >
                      {token.token}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex h-full min-h-[132px] flex-col items-center justify-center text-center">
                <Sparkles size={18} className="text-lime" />
                <p className="mt-2 text-[11px] font-semibold">Prediction + exact linear SHAP</p>
                <p className="mt-1 max-w-[220px] text-[10px] text-[var(--muted)]">
                  The same CPU model that scored the corpus will classify your text.
                </p>
              </div>
            )}
          </div>
        </div>
      </Panel>

      <Panel>
        <div className="flex flex-wrap items-center gap-2 border-b p-3" style={{ borderColor: 'var(--line-soft)' }}>
          <form
            className="relative min-w-[190px] flex-1"
            onSubmit={(event) => {
              event.preventDefault()
              setKeyword(search.trim())
            }}
          >
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
            <input
              className="field w-full !pl-8"
              placeholder="Search text or clean tokens…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </form>
          <select className="field" value={sentiment} onChange={(event) => setSentiment(event.target.value)}>
            <option value="">All sentiments</option>
            {LABELS.map((label) => (
              <option key={label}>{label}</option>
            ))}
          </select>
          <select className="field" value={sort} onChange={(event) => setSort(event.target.value)}>
            <option value="date_desc">Newest first</option>
            <option value="date_asc">Oldest first</option>
            <option value="confidence_desc">Highest confidence</option>
          </select>
          <button className="btn" type="button" onClick={() => setKeyword(search.trim())}>
            Apply
          </button>
          {(keyword || sentiment) && (
            <button
              className="btn btn-ghost"
              type="button"
              onClick={() => {
                setKeyword('')
                setSearch('')
                setSentiment('')
              }}
            >
              Clear
            </button>
          )}
        </div>

        {posts.loading ? (
          <div className="p-4"><LoadingState label="Loading posts" /></div>
        ) : posts.error ? (
          <div className="p-4"><ErrorState message={posts.error} onRetry={posts.reload} /></div>
        ) : !posts.data?.items.length ? (
          <div className="p-4"><EmptyState /></div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] border-collapse text-left">
                <thead>
                  <tr className="border-b text-[9px] uppercase tracking-[0.12em] text-[var(--muted-2)]" style={{ borderColor: 'var(--line-soft)' }}>
                    <th className="px-4 py-2.5 font-medium">Post</th>
                    <th className="hidden px-3 py-2.5 font-medium md:table-cell">Platform</th>
                    <th className="hidden px-3 py-2.5 font-medium lg:table-cell">Topic</th>
                    <th className="px-3 py-2.5 font-medium">Sentiment</th>
                    <th className="hidden px-3 py-2.5 text-right font-medium sm:table-cell">Confidence</th>
                    <th className="px-4 py-2.5 text-right font-medium">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {posts.data.items.map((post) => (
                    <tr
                      key={post.post_id}
                      onClick={() => setSelectedId(post.post_id)}
                      className="cursor-pointer border-b text-[12px] transition-colors hover:bg-[color-mix(in_srgb,var(--lime)_4%,transparent)]"
                      style={{ borderColor: 'var(--line-soft)' }}
                    >
                      <td className="max-w-[520px] px-4 py-3">
                        <p className="line-clamp-2 leading-relaxed">{post.text}</p>
                        <p className="mono mt-1 text-[9px] text-[var(--muted-2)]">
                          {post.post_id}
                          {/* Narrow viewports hide the platform/topic columns; keep
                              that context inline instead of dropping it. */}
                          <span className="md:hidden"> · {post.platform}</span>
                          <span className="lg:hidden"> · {post.topic}</span>
                        </p>
                      </td>
                      <td className="hidden whitespace-nowrap px-3 py-3 text-[11px] text-[var(--muted)] md:table-cell">{post.platform}</td>
                      <td className="hidden whitespace-nowrap px-3 py-3 text-[11px] text-[var(--muted)] lg:table-cell">{post.topic}</td>
                      <td className="px-3 py-3"><SentimentBadge sentiment={post.sentiment} /></td>
                      <td className="mono hidden px-3 py-3 text-right text-[11px] text-[var(--muted)] sm:table-cell">
                        {post.confidence != null ? `${(post.confidence * 100).toFixed(1)}%` : '—'}
                      </td>
                      <td className="mono whitespace-nowrap px-4 py-3 text-right text-[10px] text-[var(--muted-2)]">
                        {post.date?.slice(0, 10)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-[10.5px] text-[var(--muted)]">
              <span className="mono">
                {posts.data.total.toLocaleString()} matches · page {page + 1} / {totalPages.toLocaleString()}
              </span>
              <div className="flex gap-2">
                <button className="btn !min-h-8 !px-2.5 !py-1" disabled={page === 0} onClick={() => setPage((value) => value - 1)}>
                  <ArrowLeft size={12} /> Prev
                </button>
                <button
                  className="btn !min-h-8 !px-2.5 !py-1"
                  disabled={page + 1 >= totalPages}
                  onClick={() => setPage((value) => value + 1)}
                >
                  Next <ArrowRight size={12} />
                </button>
              </div>
            </div>
          </>
        )}
      </Panel>

      {selectedId && (
        <div className="fixed inset-0 z-[60] flex justify-end bg-black/55 backdrop-blur-sm" onClick={() => setSelectedId(null)}>
          <aside
            className="h-full w-full max-w-[560px] overflow-y-auto border-l p-5 shadow-2xl scrollbar-thin sm:p-6"
            style={{ borderColor: 'var(--line)', background: 'var(--ink-soft)' }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="eyebrow">Post evidence</p>
                <h2 className="mt-1 text-[22px]">Inspect prediction</h2>
              </div>
              <button className="btn btn-ghost h-8 w-8 p-0" onClick={() => setSelectedId(null)} aria-label="Close">
                <X size={15} />
              </button>
            </div>

            {detailError ? (
              <div className="mt-6"><ErrorState message={detailError} /></div>
            ) : !detail ? (
              <div className="mt-6"><LoadingState label="Loading post detail" /></div>
            ) : (
              <div className="mt-6 space-y-5">
                <div className="panel p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <SentimentBadge sentiment={detail.sentiment} score={detail.confidence} />
                    <span className="chip">{detail.platform}</span>
                    <span className="chip">{detail.topic}</span>
                  </div>
                  <p className="mt-3 text-[13.5px] leading-relaxed">{detail.text}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {detail.hashtags.map((tag) => (
                      <span key={tag} className="chip !text-[9.5px]">{tag}</span>
                    ))}
                  </div>
                  <p className="mono mt-3 text-[9px] text-[var(--muted-2)]">
                    {detail.date?.replace('T', ' ').slice(0, 19)} · {detail.author ?? 'unknown author'}
                  </p>
                </div>

                <div className="panel p-4">
                  <p className="eyebrow text-[8px]">Model probabilities</p>
                  <div className="mt-3">
                    <ProbabilityBars probabilities={detail.probabilities} />
                  </div>
                  <p className="mono mt-3 text-[9px] text-[var(--muted-2)]">
                    {detail.model ?? 'tfidf_logreg_word12'} · {detail.model_version ?? '—'}
                  </p>
                </div>

                <div className="panel p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="eyebrow text-[8px]">Why this label?</p>
                      <p className="mt-1 text-[11px] text-[var(--muted)]">
                        Exact linear SHAP attributions toward <strong>{detail.sentiment}</strong>.
                      </p>
                    </div>
                    <MessageSquareQuote size={16} className="text-lime" />
                  </div>
                  {detail.explanation ? (
                    <div className="mt-4 space-y-2">
                      {detail.explanation.tokens.slice(0, 14).map((token) => {
                        const positive = token.weight >= 0
                        const width = Math.min(100, Math.abs(token.weight) * 9)
                        return (
                          <div key={token.token}>
                            <div className="flex justify-between text-[10.5px]">
                              <span style={{ color: positive ? 'var(--positive)' : 'var(--negative)' }}>
                                {token.token}
                              </span>
                              <span className="mono text-[var(--muted)]">{token.weight.toFixed(3)}</span>
                            </div>
                            <div className="mt-0.5 h-1 overflow-hidden rounded-full" style={{ background: 'var(--line)' }}>
                              <div
                                className="h-full rounded-full"
                                style={{
                                  width: `${width}%`,
                                  background: positive ? 'var(--positive)' : 'var(--negative)',
                                }}
                              />
                            </div>
                          </div>
                        )
                      })}
                      <p className="pt-2 text-[9px] leading-relaxed text-[var(--muted-2)]">
                        {detail.explanation.method}. Attributions explain the model, not causation.
                      </p>
                    </div>
                  ) : (
                    <p className="mt-3 text-[11px] text-[var(--muted)]">
                      {detail.explanation_error ?? 'No attribution available.'}
                    </p>
                  )}
                </div>

                <div className="panel p-4">
                  <p className="eyebrow text-[8px]">Preprocessing view</p>
                  <p className="mono mt-2 break-words text-[10.5px] leading-relaxed text-[var(--muted)]">
                    {detail.clean_text || '—'}
                  </p>
                </div>
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  )
}
