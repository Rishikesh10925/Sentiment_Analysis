import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { CalendarRange, Menu, Moon, RotateCcw, Sun } from 'lucide-react'
import { datePresets, useFilters } from '../state/filters'

const TITLES: Record<string, string> = {
  '/': 'Overview',
  '/explore': 'Content explorer',
  '/research': 'Research & evidence',
  '/alerts': 'Signal monitor',
  '/upload': 'Data ingestion',
}

function getInitialTheme(): 'dark' | 'light' {
  const saved = localStorage.getItem('signal-theme')
  return saved === 'light' ? 'light' : 'dark'
}

export function TopBar({ onMenu }: { onMenu: () => void }) {
  const { filters, setFilters, reset, meta, activeLabel } = useFilters()
  const location = useLocation()
  const [theme, setTheme] = useState<'dark' | 'light'>(getInitialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('signal-theme', theme)
  }, [theme])

  const presets = datePresets(meta)
  const currentPreset =
    presets.find((preset) => preset.start === filters.start && preset.end === filters.end)?.label ??
    'Custom'

  return (
    <header
      className="sticky top-0 z-30 border-b backdrop-blur-xl"
      style={{
        borderColor: 'var(--line)',
        background: 'color-mix(in srgb, var(--ink) 82%, transparent)',
      }}
    >
      <div className="flex items-center gap-3 px-4 py-3 sm:px-6">
        <button
          className="text-[var(--muted)] md:hidden"
          onClick={onMenu}
          aria-label="Open menu"
        >
          <Menu size={20} />
        </button>
        <div className="min-w-0 flex-1">
          <p className="eyebrow text-[8px]">Signal / {TITLES[location.pathname] ?? 'Workspace'}</p>
          <p className="truncate text-[13px] font-semibold">{activeLabel}</p>
        </div>

        <div className="hidden items-center gap-2 lg:flex">
          <div className="flex items-center gap-1.5 rounded-full border px-2.5 py-1" style={{ borderColor: 'var(--line)' }}>
            <span className="live-dot" />
            <span className="eyebrow text-[8px]">Live</span>
          </div>
          <span className="mono text-[10px] text-[var(--muted-2)]">
            {meta?.total_posts.toLocaleString() ?? '—'} rows
          </span>
        </div>

        <button
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          className="btn btn-ghost h-9 w-9 p-0"
          aria-label="Toggle colour theme"
          title="Toggle colour theme"
        >
          {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
        </button>
      </div>

      <div
        className="flex flex-wrap items-center gap-2 border-t px-4 py-2.5 sm:px-6"
        style={{ borderColor: 'var(--line-soft)' }}
      >
        <div className="flex items-center gap-1.5 text-[var(--muted)]">
          <CalendarRange size={13} />
          <span className="eyebrow text-[8px]">Period</span>
        </div>
        <select
          className="field !min-h-8 !py-1 text-[11px]"
          value={currentPreset}
          onChange={(event) => {
            const preset = presets.find((item) => item.label === event.target.value)
            if (preset) setFilters({ start: preset.start, end: preset.end })
          }}
          aria-label="Date range"
        >
          {presets.map((preset) => (
            <option key={preset.label} value={preset.label}>
              {preset.label}
            </option>
          ))}
          {currentPreset === 'Custom' && <option value="Custom">Custom</option>}
        </select>

        <span className="mx-0.5 hidden text-[var(--muted-2)] sm:inline">/</span>

        <select
          className="field !min-h-8 !py-1 text-[11px]"
          value={filters.platform}
          onChange={(event) => setFilters({ platform: event.target.value })}
          aria-label="Platform"
        >
          <option value="">All platforms</option>
          {meta?.platforms.map((platform) => (
            <option key={platform} value={platform}>
              {platform}
            </option>
          ))}
        </select>

        <select
          className="field !min-h-8 max-w-[180px] !py-1 text-[11px]"
          value={filters.topic}
          onChange={(event) => setFilters({ topic: event.target.value })}
          aria-label="Topic"
        >
          <option value="">All topics</option>
          {meta?.topics.map((topic) => (
            <option key={topic.topic} value={topic.topic}>
              {topic.topic} · {topic.count.toLocaleString()}
            </option>
          ))}
        </select>

        <select
          className="field !min-h-8 !py-1 text-[11px]"
          value={filters.granularity}
          onChange={(event) =>
            setFilters({ granularity: event.target.value as 'day' | 'week' | 'month' })
          }
          aria-label="Trend granularity"
        >
          <option value="day">Daily</option>
          <option value="week">Weekly</option>
          <option value="month">Monthly</option>
        </select>

        <button onClick={reset} className="btn btn-ghost !min-h-8 !px-2.5 !py-1 text-[11px]">
          <RotateCcw size={12} /> Reset
        </button>
      </div>
    </header>
  )
}
