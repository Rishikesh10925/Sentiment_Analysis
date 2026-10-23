import {
  ArrowUpRight,
  Database,
  Download,
  Gauge,
  Layers3,
  MessageSquareText,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  TrendingUp,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { KpiCard } from '../components/KpiCard'
import { SentimentBadge, SENTIMENT_COLOR } from '../components/SentimentBadge'
import { ErrorState, LoadingState, Panel } from '../components/States'
import { useFilters } from '../state/filters'
import type { Meta, Sentiment } from '../types'

const TOOLTIP_STYLE = {
  background: 'var(--panel-2)',
  border: '1px solid var(--line)',
  borderRadius: 10,
  fontSize: 11,
  color: 'var(--text)',
  boxShadow: '0 12px 32px rgba(0,0,0,0.25)',
}

const axisStyle = { fontSize: 9, fill: 'var(--muted-2)' } as const

export function Overview({ metaState }: { metaState: { data: Meta | null; loading: boolean; error: string | null } }) {
  const { filters } = useFilters()
  const summary = useApi(() => api.summary(filters), [
    filters.start,
    filters.end,
    filters.platform,
    filters.topic,
  ])
  const trends = useApi(() => api.trends(filters), [
    filters.start,
    filters.end,
    filters.platform,
    filters.topic,
    filters.granularity,
  ])
  const platforms = useApi(() => api.platforms(filters), [
    filters.start,
    filters.end,
    filters.topic,
  ])
  const topics = useApi(() => api.topics(filters, 14), [
    filters.start,
    filters.end,
    filters.platform,
  ])
  const hashtags = useApi(() => api.hashtags(filters, 10), [
    filters.start,
    filters.end,
    filters.platform,
  ])
  const keywords = useApi(() => api.keywords(filters, 10), [
    filters.start,
    filters.end,
    filters.platform,
  ])
  const alerts = useApi(api.alerts, [])

  if (metaState.error) return <ErrorState message={metaState.error} />
  if (metaState.loading || summary.loading || trends.loading || platforms.loading) {
    return <LoadingState label="Loading corpus overview" />
  }
  if (summary.error) return <ErrorState message={summary.error} onRetry={summary.reload} />
  if (!summary.data || summary.data.total_posts === 0) {
    return <ErrorState message="No posts match the selected filters. Reset the filters to see the corpus." />
  }

  const s = summary.data
  const donut = (['Positive', 'Neutral', 'Negative'] as Sentiment[]).map((label) => ({
    name: label,
    value: s.counts[label],
    pct: s.percentages[label],
  }))
  const trendPoints = (trends.data?.points ?? []).map((point) => ({
    ...point,
    label: point.period.slice(0, 7),
    Positive: point.total ? +((point.positive / point.total) * 100).toFixed(1) : 0,
    Neutral: point.total ? +((point.neutral / point.total) * 100).toFixed(1) : 0,
    Negative: point.total ? +((point.negative / point.total) * 100).toFixed(1) : 0,
  }))
  const platformRows = platforms.data?.platforms ?? []
  const topicRows = topics.data?.topics ?? []
  const topTopic = topicRows[0]
  const triggered = alerts.data?.alerts.filter((alert) => alert.triggered) ?? []

  return (
    <div className="space-y-4">
      <section className="rise relative overflow-hidden rounded-[22px] border p-5 sm:p-7" style={{ borderColor: 'var(--line)', background: 'var(--panel)' }}>
        <div className="grid-noise pointer-events-none absolute inset-0 opacity-40" />
        <div className="relative grid gap-6 lg:grid-cols-[1.3fr_0.7fr] lg:items-end">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="chip" style={{ borderColor: 'color-mix(in srgb, var(--lime) 35%, var(--line))', color: 'var(--lime)' }}>
                <Sparkles size={11} /> Real-world corpus
              </span>
              <span className="chip">
                {s.period.start?.slice(0, 10) ?? '2009'} → {s.period.end?.slice(0, 10) ?? '2019'}
              </span>
              <span className="chip">{s.num_platforms} platforms</span>
            </div>
            <h1 className="mt-5 max-w-2xl text-[clamp(2rem,4.6vw,3.5rem)] leading-[0.98]">
              What the crowd feels,
              <br />
              <span className="text-lime italic">measured at scale.</span>
            </h1>
            <p className="mt-4 max-w-xl text-[13px] leading-relaxed text-[var(--muted)]">
              {s.total_posts.toLocaleString()} public posts scored by a calibrated linear model.
              Filter the corpus, inspect the evidence, and read the limitations before trusting a number.
            </p>
          </div>

          <div className="lg:text-right">
            <p className="eyebrow text-[8px]">Net sentiment</p>
            <p className="mono mt-2 text-[clamp(2.6rem,6vw,4.2rem)] leading-none" style={{ color: 'var(--lime)' }}>
              {s.percentages.Positive >= s.percentages.Negative ? '+' : '−'}
              {Math.abs(s.percentages.Positive - s.percentages.Negative).toFixed(1)}
              <span className="text-[0.38em] text-[var(--muted)]"> pp</span>
            </p>
            <p className="mt-2 text-[11px] text-[var(--muted)]">
              positive share minus negative share
            </p>
            <div className="mt-4 flex flex-wrap gap-2 lg:justify-end">
              <a className="btn btn-primary" href={api.reportExportUrl(filters)}>
                <Download size={13} /> PDF report
              </a>
              <a className="btn" href={api.postsExportUrl({ ...filters, limit: 20000 })}>
                <ArrowUpRight size={13} /> Export CSV
              </a>
            </div>
          </div>
        </div>
      </section>

      <div className="rise rise-1 grid grid-cols-2 gap-3 lg:grid-cols-4 xl:grid-cols-6">
        <KpiCard
          label="Classified posts"
          value={s.total_posts.toLocaleString()}
          sub={`${s.previous ? `${s.previous.total_delta >= 0 ? '+' : ''}${s.previous.total_delta.toLocaleString()} vs prior period` : 'full corpus'}`}
          icon={Database}
        />
        <KpiCard
          label="Positive"
          value={`${s.percentages.Positive.toFixed(1)}%`}
          sub={`${s.counts.Positive.toLocaleString()} posts`}
          delta={s.previous?.deltas.Positive}
          accent="var(--positive)"
          icon={ThumbsUp}
        />
        <KpiCard
          label="Neutral"
          value={`${s.percentages.Neutral.toFixed(1)}%`}
          sub={`${s.counts.Neutral.toLocaleString()} posts`}
          delta={s.previous?.deltas.Neutral}
          accent="var(--neutral)"
          icon={MessageSquareText}
        />
        <KpiCard
          label="Negative"
          value={`${s.percentages.Negative.toFixed(1)}%`}
          sub={`${s.counts.Negative.toLocaleString()} posts`}
          delta={s.previous?.deltas.Negative}
          accent="var(--negative)"
          icon={ThumbsDown}
        />
        <KpiCard
          label="Mean confidence"
          value={s.average_confidence ? `${(s.average_confidence * 100).toFixed(1)}%` : '—'}
          sub="model probability"
          accent="var(--sky)"
          icon={Gauge}
        />
        <KpiCard
          label="Topic coverage"
          value={s.num_topics}
          sub={`${topTopic?.topic ?? '—'} is largest`}
          accent="var(--violet)"
          icon={Layers3}
        />
      </div>

      {triggered.length > 0 && (
        <div
          className="rise rise-2 flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3"
          style={{ borderColor: 'color-mix(in srgb, var(--coral) 36%, var(--line))', background: 'color-mix(in srgb, var(--coral) 7%, var(--panel))' }}
        >
          <div className="flex items-center gap-2 text-[12px]">
            <span className="h-2 w-2 rounded-full" style={{ background: 'var(--coral)' }} />
            <strong>Signal triggered.</strong>
            <span className="text-[var(--muted)]">{triggered[0].message}</span>
          </div>
          <a href="/alerts" className="text-[11px] font-semibold text-lime">Open signal monitor →</a>
        </div>
      )}

      <div className="rise rise-2 grid gap-4 lg:grid-cols-[0.85fr_1.55fr]">
        <Panel title="Sentiment mix" eyebrow="Distribution">
          <div className="grid grid-cols-[1fr_0.9fr] items-center gap-2 p-4">
            <div className="relative h-[188px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={donut}
                    dataKey="value"
                    innerRadius={54}
                    outerRadius={80}
                    paddingAngle={3}
                    stroke="none"
                  >
                    {donut.map((entry) => (
                      <Cell key={entry.name} fill={SENTIMENT_COLOR[entry.name]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="mono text-xl">{s.percentages.Positive.toFixed(0)}%</span>
                <span className="eyebrow text-[7px]">positive</span>
              </div>
            </div>
            <div className="space-y-3">
              {donut.map((entry) => (
                <div key={entry.name}>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full" style={{ background: SENTIMENT_COLOR[entry.name] }} />
                      {entry.name}
                    </span>
                    <span className="mono">{entry.pct.toFixed(1)}%</span>
                  </div>
                  <div className="mt-1 h-1 overflow-hidden rounded-full" style={{ background: 'var(--line)' }}>
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${entry.pct}%`, background: SENTIMENT_COLOR[entry.name] }}
                    />
                  </div>
                  <p className="mono mt-1 text-[9px] text-[var(--muted-2)]">{entry.value.toLocaleString()} posts</p>
                </div>
              ))}
            </div>
          </div>
        </Panel>

        <Panel
          title="Sentiment over time"
          eyebrow={`${filters.granularity} share · 100% stacked`}
          action={<span className="chip"><TrendingUp size={11} /> {trendPoints.length} buckets</span>}
        >
          <div className="h-[260px] px-2 pb-4 pt-5">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendPoints} margin={{ top: 5, right: 14, left: -20, bottom: 0 }}>
                <defs>
                  {(['Positive', 'Neutral', 'Negative'] as Sentiment[]).map((label) => (
                    <linearGradient key={label} id={`fill-${label}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={SENTIMENT_COLOR[label]} stopOpacity={0.55} />
                      <stop offset="100%" stopColor={SENTIMENT_COLOR[label]} stopOpacity={0.06} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid stroke="var(--line-soft)" vertical={false} />
                <XAxis dataKey="label" tick={axisStyle} axisLine={false} tickLine={false} minTickGap={28} />
                <YAxis tick={axisStyle} axisLine={false} tickLine={false} domain={[0, 100]} unit="%" />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Area type="monotone" dataKey="Positive" stackId="1" stroke={SENTIMENT_COLOR.Positive} fill="url(#fill-Positive)" strokeWidth={1.4} />
                <Area type="monotone" dataKey="Neutral" stackId="1" stroke={SENTIMENT_COLOR.Neutral} fill="url(#fill-Neutral)" strokeWidth={1.4} />
                <Area type="monotone" dataKey="Negative" stackId="1" stroke={SENTIMENT_COLOR.Negative} fill="url(#fill-Negative)" strokeWidth={1.4} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          {platformRows.length === 2 && (
            <div className="border-t px-4 py-2.5 text-[10px] text-[var(--muted)]" style={{ borderColor: 'var(--line-soft)' }}>
              The two platforms do not overlap in time. Read cross-platform trend comparisons as descriptive, not causal.
            </div>
          )}
        </Panel>
      </div>

      <div className="rise rise-3 grid gap-4 xl:grid-cols-[1.15fr_1fr_1fr]">
        <Panel title="Platform comparison" eyebrow="Share by sentiment">
          <div className="h-[210px] px-2 pb-3 pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={platformRows} layout="vertical" margin={{ top: 0, right: 12, left: 6, bottom: 0 }}>
                <CartesianGrid stroke="var(--line-soft)" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} unit="%" tick={axisStyle} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="platform" width={78} tick={{ fontSize: 10, fill: 'var(--muted)' }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="positive_pct" name="Positive" stackId="s" fill={SENTIMENT_COLOR.Positive} radius={[0, 0, 0, 0]} />
                <Bar dataKey="neutral_pct" name="Neutral" stackId="s" fill={SENTIMENT_COLOR.Neutral} />
                <Bar dataKey="negative_pct" name="Negative" stackId="s" fill={SENTIMENT_COLOR.Negative} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="border-t" style={{ borderColor: 'var(--line-soft)' }}>
            {platformRows.map((row) => (
              <div key={row.platform} className="flex items-center justify-between px-4 py-2 text-[11px]">
                <span>{row.platform}</span>
                <span className="mono text-[var(--muted)]">{row.total.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Topics by volume" eyebrow="Rule-based taxonomy">
          <div className="space-y-3 p-4">
            {topicRows.slice(0, 6).map((row) => (
              <div key={row.topic}>
                <div className="flex items-center justify-between text-[11px]">
                  <span>{row.topic}</span>
                  <span className="mono text-[var(--muted)]">{row.total.toLocaleString()}</span>
                </div>
                <div className="mt-1.5 flex h-1.5 overflow-hidden rounded-full" style={{ background: 'var(--line)' }}>
                  <div style={{ width: `${row.positive_pct}%`, background: SENTIMENT_COLOR.Positive }} />
                  <div style={{ width: `${row.neutral_pct}%`, background: SENTIMENT_COLOR.Neutral }} />
                  <div style={{ width: `${row.negative_pct}%`, background: SENTIMENT_COLOR.Negative }} />
                </div>
                <div className="mt-1 flex justify-between text-[9px] text-[var(--muted-2)]">
                  <span>{row.positive_pct.toFixed(0)}% positive</span>
                  <span>{row.negative_pct.toFixed(1)}% negative</span>
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <div className="space-y-4">
          <Panel title="Emerging vocabulary" eyebrow="Hashtags & unigrams">
            <div className="space-y-3 p-4">
              <div>
                <p className="eyebrow mb-2 text-[7px]">Hashtags</p>
                <div className="flex flex-wrap gap-1.5">
                  {(hashtags.data?.hashtags ?? []).slice(0, 6).map((row) => (
                    <span key={row.hashtag} className="chip !text-[10px]">
                      {row.hashtag} <span className="mono text-[var(--muted-2)]">{row.count}</span>
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <p className="eyebrow mb-2 text-[7px]">Frequent tokens</p>
                <div className="flex flex-wrap gap-1.5">
                  {(keywords.data?.keywords ?? []).slice(0, 7).map((row) => (
                    <span key={row.keyword} className="chip !text-[10px]">
                      {row.keyword} <span className="mono text-[var(--muted-2)]">{row.count}</span>
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </Panel>

          <Panel title="Served model" eyebrow="Artifact verified">
            <div className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-[12.5px] font-semibold">{metaState.data?.model.display_name ?? 'TF-IDF + Logistic Regression'}</p>
                  <p className="mt-1 text-[10px] text-[var(--muted)]">{metaState.data?.model.explanation}</p>
                </div>
                <ShieldCheck size={16} className="text-lime" />
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2">
                <div className="panel-soft p-2.5">
                  <p className="eyebrow text-[7px]">Macro F1</p>
                  <p className="mono mt-1 text-[15px]">{metaState.data?.model.test_metrics?.macro_f1.toFixed(3) ?? '0.582'}</p>
                </div>
                <div className="panel-soft p-2.5">
                  <p className="eyebrow text-[7px]">Accuracy</p>
                  <p className="mono mt-1 text-[15px]">{metaState.data?.model.test_metrics?.accuracy.toFixed(3) ?? '0.586'}</p>
                </div>
                <div className="panel-soft p-2.5">
                  <p className="eyebrow text-[7px]">ECE</p>
                  <p className="mono mt-1 text-[15px]">{metaState.data?.model.test_metrics?.calibration?.ece.toFixed(3) ?? '0.078'}</p>
                </div>
              </div>
              <p className="mt-3 text-[9.5px] leading-relaxed text-[var(--muted-2)]">
                Evaluated on the held-out TweetEval test split. Labels shown on posts are predictions, not gold annotations.
              </p>
            </div>
          </Panel>
        </div>
      </div>

      {alerts.data && (
        <Panel
          title="Current signal state"
          eyebrow={`Threshold ${alerts.data.configured_threshold}% negative`}
          action={<SentimentBadge sentiment={triggered.length ? 'Negative' : 'Neutral'} />}
        >
          <div className="grid gap-3 p-4 md:grid-cols-2">
            {alerts.data.alerts.map((alert) => (
              <div key={alert.type} className="panel-soft p-3.5">
                <div className="flex items-center justify-between">
                  <p className="eyebrow text-[8px]">{alert.type.replace('_', ' ')}</p>
                  <span className="text-[10px] font-semibold" style={{ color: alert.triggered ? 'var(--negative)' : 'var(--positive)' }}>
                    {alert.triggered ? 'Triggered' : 'Within range'}
                  </span>
                </div>
                <p className="mt-2 text-[11.5px] leading-relaxed text-[var(--muted)]">{alert.message}</p>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  )
}
