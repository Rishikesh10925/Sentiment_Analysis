import { useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, FileText, Loader2, UploadCloud, XCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { AlertRow, Summary } from '../types'

interface UploadResult {
  filename: string
  validation_report: {
    total_rows: number
    missing_values: Record<string, number>
    duplicate_post_ids: number
    invalid_platform_count: number
    invalid_date_count: number
    platform_counts: Record<string, number>
  }
  analyzed: boolean
  db_loaded?: boolean
  db_error?: string
  spark_report?: {
    rows_ingested_raw: number
    rows_after_missing_text_drop: number
    rows_after_dedup: number
    rows_matched_with_predictions: number
    overall_negative_percentage: number
  }
  summary?: Summary
  alerts?: AlertRow[]
  next_steps: string
}

export function UploadPage() {
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [result, setResult] = useState<UploadResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [stage, setStage] = useState<'idle' | 'uploading' | 'analyzing'>('idle')
  const inputRef = useRef<HTMLInputElement>(null)

  function pickFile(file: File) {
    setError(null)
    setResult(null)
    setPendingFile(file)
  }

  async function confirmUpload(analyze: boolean) {
    if (!pendingFile) return
    const file = pendingFile
    setPendingFile(null)
    setStage('uploading')
    setError(null)
    const analyzingTimer = analyze ? setTimeout(() => setStage('analyzing'), 600) : null
    try {
      const body = (await api.upload(file, analyze)) as UploadResult
      setResult(body)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed.')
    } finally {
      if (analyzingTimer) clearTimeout(analyzingTimer)
      setStage('idle')
    }
  }

  return (
    <div className="space-y-6 max-w-2xl mx-auto text-center">
      <div>
        <h1 className="text-xl font-semibold">Upload Data</h1>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          Upload a CSV with columns: id, platform, post_id, author, text, date, topic, hashtags. You'll be asked to
          confirm before anything runs.
        </p>
      </div>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault()
          const file = e.dataTransfer.files[0]
          if (file) pickFile(file)
        }}
        className="rounded-xl border-2 border-dashed border-[var(--color-border)] bg-[var(--color-surface)] p-10 flex flex-col items-center justify-center gap-3 cursor-pointer hover:border-indigo-400 transition-colors"
      >
        {stage !== 'idle' ? (
          <Loader2 size={32} className="text-indigo-500 animate-spin" />
        ) : (
          <UploadCloud size={32} className="text-[var(--color-text-muted)]" />
        )}
        <p className="text-sm text-[var(--color-text-muted)]">
          {stage === 'uploading' && 'Uploading...'}
          {stage === 'analyzing' && 'Running full analysis (cleaning → ML → Spark → database)...'}
          {stage === 'idle' && 'Click or drag a .csv file here'}
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) pickFile(file)
            e.target.value = ''
          }}
        />
      </div>

      {pendingFile && (
        <div className="rounded-xl border border-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 p-4 space-y-3">
          <div className="flex items-start gap-2.5">
            <FileText size={18} className="text-indigo-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium">{pendingFile.name}</p>
              <p className="text-xs text-[var(--color-text-muted)]">
                {(pendingFile.size / 1024).toFixed(1)} KB — choose what to do with this file:
              </p>
            </div>
          </div>

          <div className="flex items-start gap-2.5 rounded-lg bg-white/60 dark:bg-black/20 px-3 py-2 text-xs text-[var(--color-text-muted)]">
            <AlertTriangle size={14} className="text-amber-500 shrink-0 mt-0.5" />
            <span>
              <strong>Analyze &amp; Replace Dashboard</strong> runs the full pipeline and overwrites the dashboard's
              current data with this file's results. <strong>Validate Only</strong> just checks the file's format
              and does not touch the dashboard.
            </span>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => confirmUpload(true)}
              className="rounded-md bg-indigo-600 text-white px-3 py-1.5 text-sm font-medium hover:bg-indigo-700 transition-colors"
            >
              Analyze &amp; Replace Dashboard
            </button>
            <button
              onClick={() => confirmUpload(false)}
              className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-sm font-medium hover:bg-[var(--color-bg)] transition-colors"
            >
              Validate Only
            </button>
            <button
              onClick={() => setPendingFile(null)}
              className="rounded-md px-3 py-1.5 text-sm font-medium text-[var(--color-text-muted)] hover:bg-[var(--color-bg)] transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2.5 rounded-lg border border-[var(--color-negative)]/30 bg-[var(--color-negative-bg)] px-4 py-3 text-sm text-[var(--color-negative)]">
          <XCircle size={18} className="shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {result && (
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 space-y-4">
          <div className="flex items-center gap-2 text-[var(--color-positive)]">
            <CheckCircle2 size={18} />
            <p className="text-sm font-medium">{result.filename} validated successfully</p>
          </div>

          <dl className="grid grid-cols-2 gap-y-2 text-sm">
            <dt className="text-[var(--color-text-muted)]">Total rows</dt>
            <dd className="text-right tabular-nums">{result.validation_report.total_rows.toLocaleString()}</dd>
            <dt className="text-[var(--color-text-muted)]">Duplicate post IDs</dt>
            <dd className="text-right tabular-nums">{result.validation_report.duplicate_post_ids}</dd>
            <dt className="text-[var(--color-text-muted)]">Invalid platforms</dt>
            <dd className="text-right tabular-nums">{result.validation_report.invalid_platform_count}</dd>
            <dt className="text-[var(--color-text-muted)]">Invalid dates</dt>
            <dd className="text-right tabular-nums">{result.validation_report.invalid_date_count}</dd>
          </dl>

          {result.summary && (
            <div className="border-t border-[var(--color-border)] pt-4">
              <p className="text-sm font-medium mb-2">Full analysis result</p>
              <dl className="grid grid-cols-2 gap-y-2 text-sm">
                <dt className="text-[var(--color-text-muted)]">Posts analyzed</dt>
                <dd className="text-right tabular-nums">{result.summary.total_posts.toLocaleString()}</dd>
                <dt className="text-[var(--color-positive)]">Positive</dt>
                <dd className="text-right tabular-nums text-[var(--color-positive)]">{result.summary.positive_pct}%</dd>
                <dt className="text-[var(--color-neutral)]">Neutral</dt>
                <dd className="text-right tabular-nums text-[var(--color-neutral)]">{result.summary.neutral_pct}%</dd>
                <dt className="text-[var(--color-negative)]">Negative</dt>
                <dd className="text-right tabular-nums text-[var(--color-negative)]">{result.summary.negative_pct}%</dd>
              </dl>

              {result.alerts?.some((a) => a.triggered) && (
                <div className="mt-3 space-y-1.5">
                  {result.alerts.filter((a) => a.triggered).map((a) => (
                    <p key={a.type} className="text-xs text-[var(--color-negative)] bg-[var(--color-negative-bg)] rounded-md px-2.5 py-1.5">
                      {a.message}
                    </p>
                  ))}
                </div>
              )}

              <Link
                to="/"
                className="mt-3 inline-block rounded-md bg-indigo-600 text-white px-3 py-1.5 text-sm font-medium hover:bg-indigo-700 transition-colors"
              >
                View Dashboard →
              </Link>
            </div>
          )}

          {result.db_error && (
            <p className="text-xs text-[var(--color-negative)] border-t border-[var(--color-border)] pt-3">
              {result.db_error}
            </p>
          )}

          <p className="text-xs text-[var(--color-text-muted)] border-t border-[var(--color-border)] pt-3">
            {result.next_steps}
          </p>
        </div>
      )}
    </div>
  )
}
