import { describe, expect, it } from 'vitest'

import type { Filters, Meta } from '../types'
import { datePresets, describeFilters } from './filters'

const meta = {
  date_range: { min: '2009-04-06T00:00:00', max: '2019-02-01T12:00:00' },
} as Meta

describe('describeFilters', () => {
  it('labels an empty selection as all data', () => {
    expect(describeFilters({})).toBe('All time · All platforms · All topics')
  })

  it('shows an open-ended start date as "start"', () => {
    expect(describeFilters({ end: '2019-02-01' })).toBe('start → 2019-02-01 · All platforms · All topics')
  })

  it('shows an open-ended end date as "latest"', () => {
    expect(describeFilters({ start: '2009-04-06' })).toBe('2009-04-06 → latest · All platforms · All topics')
  })

  it('includes platform and topic when selected', () => {
    const filters: Partial<Filters> = {
      start: '2009-04-06',
      end: '2009-06-30',
      platform: 'X',
      topic: 'Technology',
    }
    expect(describeFilters(filters)).toBe('2009-04-06 → 2009-06-30 · X · Technology')
  })
})

describe('datePresets', () => {
  it('returns the fixed corpus presets plus the metadata range', () => {
    const presets = datePresets(meta)
    expect(presets.map((preset) => preset.label)).toEqual([
      'All time',
      '2009 X corpus',
      '2019 Reddit',
      'Full range',
    ])
    expect(presets[0]).toEqual({ label: 'All time', start: '', end: '' })
    expect(presets[3]).toEqual({ label: 'Full range', start: '2009-04-06', end: '2019-02-01' })
  })

  it('degrades to empty bounds while metadata is still loading', () => {
    expect(datePresets(null)[3]).toEqual({ label: 'Full range', start: '', end: '' })
  })
})
