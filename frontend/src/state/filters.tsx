import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { Filters, Meta } from '../types'

const EMPTY: Filters = {
  start: '',
  end: '',
  platform: '',
  topic: '',
  granularity: 'month',
}

interface FilterContextValue {
  filters: Filters
  setFilters: (patch: Partial<Filters>) => void
  reset: () => void
  meta: Meta | null
  activeLabel: string
}

const FilterContext = createContext<FilterContextValue | null>(null)

/** Human-readable summary of the active date/platform/topic selection. */
export function describeFilters(filters: Partial<Filters>): string {
  const parts = [
    filters.start || filters.end ? `${filters.start || 'start'} → ${filters.end || 'latest'}` : 'All time',
    filters.platform || 'All platforms',
    filters.topic || 'All topics',
  ]
  return parts.join(' · ')
}

export function FilterProvider({ meta, children }: { meta: Meta | null; children: ReactNode }) {
  const [filters, setState] = useState<Filters>(EMPTY)

  const value = useMemo<FilterContextValue>(() => {
    const setFilters = (patch: Partial<Filters>) =>
      setState((current) => ({ ...current, ...patch }))
    const reset = () => setState(EMPTY)
    return {
      filters,
      setFilters,
      reset,
      meta,
      activeLabel: describeFilters(filters),
    }
  }, [filters, meta])

  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>
}

export function useFilters(): FilterContextValue {
  const context = useContext(FilterContext)
  if (!context) throw new Error('useFilters must be used inside FilterProvider')
  return context
}

export interface DatePreset {
  label: string
  start: string
  end: string
}

export function datePresets(meta: Meta | null): DatePreset[] {
  const min = meta?.date_range.min?.slice(0, 10) ?? ''
  const max = meta?.date_range.max?.slice(0, 10) ?? ''
  return [
    { label: 'All time', start: '', end: '' },
    { label: '2009 X corpus', start: '2009-04-01', end: '2009-06-30' },
    { label: '2019 Reddit', start: '2019-01-01', end: '2019-02-01' },
    { label: 'Full range', start: min, end: max },
  ]
}
