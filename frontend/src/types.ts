export type Sentiment = 'Positive' | 'Neutral' | 'Negative'

export interface ModelInfo {
  name: string
  display_name: string
  labels: string[]
  available: boolean
  explanation: string
  artifact_sha256_12?: string
  size_kb?: number
  test_metrics?: {
    accuracy: number
    macro_f1: number
    weighted_f1: number
    bootstrap_macro_f1?: { mean: number; ci95_low: number; ci95_high: number }
    calibration?: { ece: number; brier: number }
  }
  training?: { train_rows: number; test_rows: number; labels: string[] }
  transformer_checkpoint?: { available: boolean; fine_tuned: boolean; serving_default: boolean }
}

export interface Meta {
  app: string
  environment: string
  total_posts: number
  date_range: { min: string | null; max: string | null }
  platforms: string[]
  topics: { topic: string; count: number }[]
  labels: Sentiment[]
  model: ModelInfo
  provenance: {
    sources: {
      name: string
      citation: string
      url: string
      usage: string
      sha256?: string
    }[]
    generated_at: string | null
    rows_by_platform: Record<string, number>
    notes: string[]
  }
  research: {
    available: boolean
    transformer_available: boolean
    absa_available: boolean
    spark_available: boolean
  }
}

export interface Summary {
  period: { start: string | null; end: string | null }
  total_posts: number
  counts: Record<Sentiment, number>
  percentages: Record<Sentiment, number>
  average_confidence: number | null
  num_platforms: number
  num_topics: number
  previous: null | {
    total: number
    percentages: Record<Sentiment, number>
    deltas: Record<Sentiment, number>
    total_delta: number
  }
}

export interface TrendPoint {
  period: string
  total: number
  positive: number
  neutral: number
  negative: number
  negative_pct: number
}

export interface PlatformRow {
  platform: string
  Positive: number
  Neutral: number
  Negative: number
  total: number
  positive_pct: number
  neutral_pct: number
  negative_pct: number
}

export interface TopicRow {
  topic: string
  Positive: number
  Neutral: number
  Negative: number
  total: number
  positive_pct: number
  neutral_pct: number
  negative_pct: number
  negative_rate: number
}

export interface TagRow {
  hashtag?: string
  keyword?: string
  count: number
}

export interface AlertsResponse {
  configured_threshold: number
  alerts: {
    type: string
    triggered: boolean
    message: string | null
    threshold: number | null
    negative_percentage: number | null
    major_topic: string | null
    created_at: string | null
  }[]
}

export interface Post {
  post_id: string
  platform: string
  author: string | null
  date: string | null
  topic: string | null
  hashtags: string[]
  text: string
  sentiment: Sentiment
  confidence: number | null
  probabilities: Record<Sentiment, number | null>
}

export interface PostsResponse {
  total: number
  limit: number
  offset: number
  items: Post[]
}

export interface TokenAttribution {
  token: string
  weight: number
  direction: 'supports' | 'opposes'
}

export interface Explanation {
  text: string
  sentiment: Sentiment
  probabilities: Record<Sentiment, number> | null
  model: string
  method: string
  tokens: TokenAttribution[]
  base_value_note?: string
}

export interface PostDetail extends Post {
  clean_text: string
  model: string | null
  model_version: string | null
  explanation?: Explanation
  explanation_error?: string
}

export interface PredictResponse {
  sentiment: Sentiment
  confidence: number
  probabilities: Record<Sentiment, number>
  explanation: Explanation
  model: ModelInfo
}

export interface LeaderboardRow {
  model: string
  macro_f1: number
  accuracy: number
  macro_f1_ci?: { mean: number; ci95_low: number; ci95_high: number }
  ece?: number | null
  train_seconds?: number | null
}

export interface ResearchPayload {
  available: Record<string, boolean>
  limitations: string[]
  baselines?: Record<string, unknown> & {
    dataset?: Record<string, unknown>
    ablations?: { name: string; variant: string; delta_macro_f1: number }[]
    learning_curve?: { train_rows: number; macro_f1: number }[]
    domain_shift?: Record<string, Record<string, number>>
    error_examples?: { text: string; gold: string; predicted: string; confidence: number }[]
  }
  transformer?: Record<string, unknown> & {
    macro_f1?: number
    accuracy?: number
    device?: string
    history?: { epoch: number; train_loss: number; val_macro_f1: number }[]
  }
  external_roberta?: Record<string, unknown> & { macro_f1?: number; accuracy?: number }
  absa?: Record<string, unknown>
  explainability?: Record<string, unknown>
  spark_benchmark?: {
    environment?: Record<string, unknown>
    methodology?: string
    runs?: {
      rows: number
      method: string
      seconds: number
      rows_per_second: number
      speedup_vs_naive?: number
      matches_naive?: boolean
    }[]
    partition_sweep?: { rows: number; shuffle_partitions: number; seconds: number }[]
  }
  leaderboard: LeaderboardRow[]
  provenance: {
    generated_at?: string
    rows?: number
    rows_by_platform?: Record<string, number>
    sources?: { name: string; citation: string; url: string }[]
    notes?: string[]
  }
}

export interface Filters {
  start: string
  end: string
  platform: string
  topic: string
  granularity: 'day' | 'week' | 'month'
}

export interface PostsFilters extends Partial<Filters> {
  sentiment?: string
  keyword?: string
  sort?: string
  limit?: number
  offset?: number
}
