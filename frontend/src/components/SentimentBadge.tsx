import type { Sentiment } from '../types'

const styles: Record<Sentiment, string> = {
  Positive: 'text-[var(--color-positive)] bg-[var(--color-positive-bg)]',
  Neutral: 'text-[var(--color-neutral)] bg-[var(--color-neutral-bg)]',
  Negative: 'text-[var(--color-negative)] bg-[var(--color-negative-bg)]',
}

export function SentimentBadge({ sentiment }: { sentiment: Sentiment }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[sentiment]}`}>
      {sentiment}
    </span>
  )
}

export const SENTIMENT_COLOR: Record<Sentiment, string> = {
  Positive: 'var(--color-positive)',
  Neutral: 'var(--color-neutral)',
  Negative: 'var(--color-negative)',
}

export const PLATFORM_COLORS = [
  'var(--color-platform-1)',
  'var(--color-platform-2)',
  'var(--color-platform-3)',
  'var(--color-platform-4)',
  'var(--color-platform-5)',
  'var(--color-platform-6)',
]
