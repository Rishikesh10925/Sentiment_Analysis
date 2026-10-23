import type {
  AlertsResponse,
  Filters,
  Meta,
  PlatformRow,
  PostDetail,
  PostsFilters,
  PostsResponse,
  PredictResponse,
  ResearchPayload,
  Summary,
  TagRow,
  TopicRow,
  TrendPoint,
} from '../types'

/**
 * Empty in the default single-origin deployment (the reverse proxy / dev
 * server forwards /api). Set VITE_API_BASE_URL when the frontend is hosted
 * separately from the API, e.g. a Render static site calling the API
 * service directly.
 */
const ORIGIN = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')
const BASE = `${ORIGIN}/api/v2`

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type Params = Record<string, string | number | boolean | undefined | null>

export function buildQuery(params?: Params): string {
  if (!params) return ''
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value))
    }
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

export function filterParams(filters: Partial<Filters>): Params {
  return {
    start: filters.start || undefined,
    end: filters.end || undefined,
    platform: filters.platform || undefined,
    topic: filters.topic || undefined,
  }
}

async function requestJson<T>(path: string, params?: Params, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}${buildQuery(params)}`, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new ApiError(response.status, body.detail ?? `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => fetch(`${ORIGIN}/api/health`).then((res) => res.json() as Promise<{ status: string }>),
  meta: () => requestJson<Meta>('/meta'),
  summary: (filters: Partial<Filters>) =>
    requestJson<Summary>('/summary', { ...filterParams(filters), compare: true }),
  trends: (filters: Partial<Filters>) =>
    requestJson<{ granularity: string; points: TrendPoint[] }>('/trends', {
      ...filterParams(filters),
      granularity: filters.granularity ?? 'month',
    }),
  platforms: (filters: Partial<Filters>) =>
    requestJson<{ platforms: PlatformRow[] }>('/platforms', filterParams(filters)),
  topics: (filters: Partial<Filters>, limit = 20) =>
    requestJson<{ topics: TopicRow[]; total_topics: number }>('/topics', {
      ...filterParams(filters),
      limit,
    }),
  hashtags: (filters: Partial<Filters>, limit = 12) =>
    requestJson<{ hashtags: TagRow[] }>('/hashtags', {
      ...filterParams(filters),
      limit,
    }),
  keywords: (filters: Partial<Filters>, limit = 12) =>
    requestJson<{ keywords: TagRow[] }>('/keywords', {
      ...filterParams(filters),
      limit,
    }),
  alerts: () => requestJson<AlertsResponse>('/alerts'),
  research: () => requestJson<ResearchPayload>('/research'),
  posts: (filters: PostsFilters) => requestJson<PostsResponse>('/posts', { ...filters }),
  post: (postId: string) => requestJson<PostDetail>(`/posts/${encodeURIComponent(postId)}`),
  predict: (text: string) =>
    requestJson<PredictResponse>('/predict', undefined, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }),
  explain: (text: string) =>
    requestJson<PostDetail['explanation']>('/explain', undefined, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }),
  postsExportUrl: (filters: PostsFilters) =>
    `${BASE}/export/posts.csv${buildQuery({ ...filters, limit: undefined, offset: undefined })}`,
  reportExportUrl: (filters: Partial<Filters>) =>
    `${BASE}/export/report.pdf${buildQuery(filterParams(filters))}`,
  upload: async (file: File, analyze: boolean, apiKey: string) => {
    const form = new FormData()
    form.append('file', file)
    const response = await fetch(`${ORIGIN}/api/upload${buildQuery({ analyze })}`, {
      method: 'POST',
      body: form,
      headers: apiKey ? { 'X-API-Key': apiKey } : undefined,
    })
    const body = await response.json().catch(() => ({}))
    if (!response.ok) throw new ApiError(response.status, body.detail ?? 'Upload failed')
    return body
  },
}
