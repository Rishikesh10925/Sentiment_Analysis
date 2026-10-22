import type {
  AlertRow,
  HashtagRow,
  KeywordRow,
  NegativePost,
  PlatformRow,
  PostsFilters,
  PostsResponse,
  SentimentRow,
  Summary,
  TopicRow,
  TrendPoint,
} from '../types'

const BASE = '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function getJson<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== '') url.searchParams.set(key, String(value))
    }
  }
  const res = await fetch(url.toString().replace(window.location.origin, ''))
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.detail ?? `Request failed: ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => getJson<{ status: string }>('/health'),
  summary: () => getJson<Summary>('/dashboard/summary'),
  sentiment: () => getJson<SentimentRow[]>('/dashboard/sentiment'),
  platforms: () => getJson<PlatformRow[]>('/dashboard/platforms'),
  topics: () => getJson<TopicRow[]>('/dashboard/topics'),
  trends: (granularity: 'day' | 'week' | 'month') =>
    getJson<TrendPoint[]>('/dashboard/trends', { granularity }),
  hashtags: (limit = 30) => getJson<HashtagRow[]>('/dashboard/hashtags', { limit }),
  keywords: (limit = 30) => getJson<KeywordRow[]>('/dashboard/keywords', { limit }),
  negativePosts: (limit = 20) => getJson<NegativePost[]>('/dashboard/negative-posts', { limit }),
  alerts: () => getJson<AlertRow[]>('/dashboard/alerts'),
  posts: (filters: PostsFilters) => getJson<PostsResponse>('/posts', { ...filters }),
  upload: async (file: File, analyze: boolean) => {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${BASE}/upload?analyze=${analyze}`, { method: 'POST', body: form })
    const body = await res.json().catch(() => ({}))
    if (!res.ok) throw new ApiError(res.status, body.detail ?? 'Upload failed')
    return body
  },
}
