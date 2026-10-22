export type Sentiment = 'Positive' | 'Neutral' | 'Negative'

export interface Summary {
  total_posts: number
  positive_count: number
  neutral_count: number
  negative_count: number
  positive_pct: number
  neutral_pct: number
  negative_pct: number
  num_platforms: number
  num_topics: number
}

export interface SentimentRow {
  sentiment: Sentiment
  count: number
  percentage: number
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
}

export interface TrendPoint {
  period: string
  positive: number
  neutral: number
  negative: number
  total: number
  negative_pct: number
}

export interface HashtagRow {
  hashtag: string
  count: number
  [key: string]: string | number
}

export interface KeywordRow {
  keyword: string
  count: number
  [key: string]: string | number
}

export interface NegativePost {
  post_id: string
  platform: string
  topic: string
  original_text: string
  sentiment: Sentiment
  confidence: number | null
  date: string | null
}

export interface AlertRow {
  type: 'negative_threshold' | 'period_change'
  triggered: boolean
  message: string | null
  threshold: number | null
  negative_percentage: number | null
  major_topic: string | null
  created_at: string | null
}

export interface Post {
  post_id: string
  platform: string
  author: string
  date: string | null
  topic: string
  hashtags: string
  original_text: string
  clean_text: string
  sentiment: Sentiment
  confidence: number | null
}

export interface PostsResponse {
  total: number
  limit: number
  offset: number
  items: Post[]
}

export interface PostsFilters {
  platform?: string
  sentiment?: string
  topic?: string
  date?: string
  keyword?: string
  limit?: number
  offset?: number
}
