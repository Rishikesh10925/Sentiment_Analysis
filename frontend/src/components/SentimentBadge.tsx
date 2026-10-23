import type { Sentiment } from '../types'

export const SENTIMENT_COLOR: Record<Sentiment, string> = {
  Positive: 'var(--positive)',
  Neutral: 'var(--neutral)',
  Negative: 'var(--negative)',
}

export function SentimentBadge({ sentiment, score }: { sentiment: Sentiment; score?: number | null }) {
  const colour = SENTIMENT_COLOR[sentiment]
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10.5px] font-semibold"
      style={{
        color: colour,
        background: `color-mix(in srgb, ${colour} 12%, transparent)`,
        border: `1px solid color-mix(in srgb, ${colour} 28%, transparent)`,
      }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: colour }} />
      {sentiment}
      {score != null && <span className="mono opacity-70">{Math.round(score * 100)}%</span>}
    </span>
  )
}
