import { describe, expect, it } from 'vitest'

import { ApiError, buildQuery, filterParams } from './client'

describe('buildQuery', () => {
  it('returns an empty string when there are no params', () => {
    expect(buildQuery()).toBe('')
    expect(buildQuery({})).toBe('')
  })

  it('drops empty, null and undefined values', () => {
    expect(buildQuery({ a: '', b: null, c: undefined, d: 'kept' })).toBe('?d=kept')
  })

  it('keeps falsy numbers and booleans', () => {
    expect(buildQuery({ limit: 0, offset: 0, compare: false })).toBe('?limit=0&offset=0&compare=false')
  })

  it('url-encodes reserved characters', () => {
    const query = buildQuery({ keyword: 'a&b=c d', topic: 'Health & Science' })
    expect(query).toBe('?keyword=a%26b%3Dc+d&topic=Health+%26+Science')
  })

  it('preserves parameter order for stable cache keys', () => {
    expect(buildQuery({ start: '2020-01-01', end: '2020-12-31', platform: 'X' })).toBe(
      '?start=2020-01-01&end=2020-12-31&platform=X',
    )
  })
})

describe('filterParams', () => {
  it('maps set filters to query params', () => {
    expect(filterParams({ start: '2019-01-01', platform: 'Reddit', topic: 'Health' })).toEqual({
      start: '2019-01-01',
      end: undefined,
      platform: 'Reddit',
      topic: 'Health',
    })
  })

  it('normalises blank selections to undefined so the API sees "all"', () => {
    const params = filterParams({ start: '', end: '', platform: '', topic: '' })
    expect(Object.values(params).every((value) => value === undefined)).toBe(true)
  })

  it('ignores granularity, which belongs to the trends endpoint only', () => {
    expect(filterParams({ granularity: 'week' })).not.toHaveProperty('granularity')
  })
})

describe('ApiError', () => {
  it('carries the HTTP status and message', () => {
    const error = new ApiError(503, 'database unavailable')
    expect(error).toBeInstanceOf(Error)
    expect(error.status).toBe(503)
    expect(error.message).toBe('database unavailable')
  })
})
