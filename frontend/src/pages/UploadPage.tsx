import { useRef, useState } from 'react'
import { AlertTriangle, FileCheck2, FileSpreadsheet, KeyRound, Loader2, UploadCloud } from 'lucide-react'
import { api } from '../api/client'
import { Panel } from '../components/States'

const REQUIRED_COLUMNS = ['id', 'platform', 'post_id', 'author', 'text', 'date', 'topic', 'hashtags']

export function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem('signal-api-key') ?? '')
  const [analyze, setAnalyze] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function chooseFile(candidate: File | undefined) {
    if (!candidate) return
    if (!candidate.name.toLowerCase().endsWith('.csv')) {
      setError('Only .csv files are accepted.')
      return
    }
    setError(null)
    setResult(null)
    setFile(candidate)
  }

  async function submit() {
    if (!file) return
    setBusy(true)
    setError(null)
    setResult(null)
    sessionStorage.setItem('signal-api-key', apiKey)
    try {
      const payload = await api.upload(file, analyze, apiKey)
      setResult(payload)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setBusy(false)
    }
  }

  const report = result?.validation_report as
    | { total_rows?: number; duplicate_rows?: number; missing_values?: Record<string, number> }
    | undefined

  return (
    <div className="space-y-4">
      <div>
        <p className="eyebrow">Operator surface</p>
        <h1 className="mt-1 text-[30px] leading-tight">Data ingestion</h1>
        <p className="mt-1 max-w-2xl text-[12.5px] leading-relaxed text-[var(--muted)]">
          Validate a CSV against the pipeline schema, or run the legacy Spark pipeline to replace the dashboard corpus.
          Uploads are the only destructive API operation and are guarded by an API key when configured.
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
        <Panel title="Upload a CSV" eyebrow="Maximum 50 MB">
          <div className="p-4">
            <div
              className={`flex min-h-[210px] cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed p-6 text-center transition-colors ${
                dragging ? 'bg-[color-mix(in_srgb,var(--lime)_6%,transparent)]' : ''
              }`}
              style={{ borderColor: dragging ? 'var(--lime)' : 'var(--line)' }}
              onClick={() => inputRef.current?.click()}
              onDragOver={(event) => {
                event.preventDefault()
                setDragging(true)
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault()
                setDragging(false)
                chooseFile(event.dataTransfer.files[0])
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => event.key === 'Enter' && inputRef.current?.click()}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(event) => chooseFile(event.target.files?.[0])}
              />
              <span
                className="flex h-12 w-12 items-center justify-center rounded-xl"
                style={{ background: 'var(--panel-2)', color: 'var(--lime)' }}
              >
                <UploadCloud size={22} />
              </span>
              <p className="mt-3 text-[13px] font-semibold">
                {file ? file.name : 'Drop a CSV here, or click to browse'}
              </p>
              <p className="mt-1 text-[10.5px] text-[var(--muted)]">
                {file ? `${(file.size / 1024).toFixed(1)} KB` : 'Required schema is shown on the right.'}
              </p>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="block">
                <span className="eyebrow flex items-center gap-1.5 text-[8px]"><KeyRound size={10} /> API key</span>
                <input
                  type="password"
                  className="field mt-1.5 w-full"
                  placeholder="Required on public deployments"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  autoComplete="off"
                />
              </label>
              <div>
                <span className="eyebrow text-[8px]">Mode</span>
                <div className="mt-1.5 flex gap-2">
                  <button
                    className={`btn flex-1 ${!analyze ? 'btn-primary' : ''}`}
                    onClick={() => setAnalyze(false)}
                    type="button"
                  >
                    Validate only
                  </button>
                  <button
                    className={`btn flex-1 ${analyze ? 'btn-primary' : ''}`}
                    onClick={() => setAnalyze(true)}
                    type="button"
                  >
                    Replace corpus
                  </button>
                </div>
              </div>
            </div>

            {analyze && (
              <div
                className="mt-3 flex gap-2 rounded-lg border px-3 py-2.5 text-[10px] leading-relaxed"
                style={{ borderColor: 'color-mix(in srgb, var(--amber) 35%, var(--line))', color: 'var(--amber)', background: 'color-mix(in srgb, var(--amber) 5%, transparent)' }}
              >
                <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                Replace mode runs the full Spark + ML pipeline and clears the dashboard tables before loading the uploaded
                file. Restore the curated corpus afterward with <code className="mono">python -m backend.db.load_real_data</code>.
              </div>
            )}

            {error && <p className="mt-3 text-[11px] text-negative">{error}</p>}

            <button
              className="btn btn-primary mt-4 w-full"
              disabled={!file || busy}
              onClick={submit}
            >
              {busy ? <Loader2 size={14} className="animate-spin" /> : <UploadCloud size={14} />}
              {busy ? 'Working…' : analyze ? 'Validate and replace corpus' : 'Validate file'}
            </button>
          </div>
        </Panel>

        <div className="space-y-4">
          <Panel title="Required schema" eyebrow="Exact column names">
            <div className="flex flex-wrap gap-1.5 p-4">
              {REQUIRED_COLUMNS.map((column) => (
                <span key={column} className="chip mono !text-[10px]">{column}</span>
              ))}
            </div>
            <p className="border-t px-4 py-3 text-[9.5px] leading-relaxed text-[var(--muted-2)]" style={{ borderColor: 'var(--line-soft)' }}>
              UTF-8 CSV. Rows are validated for missing columns, duplicate IDs and empty critical fields before any
              destructive action.
            </p>
          </Panel>

          {result && (
            <Panel title="Validation result" eyebrow="Request completed">
              <div className="p-4">
                <div className="flex items-center gap-2 text-[12px] font-semibold text-positive">
                  <FileCheck2 size={16} /> File accepted
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <div className="panel-soft p-2.5">
                    <p className="text-[9px] text-[var(--muted-2)]">Rows</p>
                    <p className="mono mt-1 text-[16px]">{report?.total_rows?.toLocaleString() ?? '—'}</p>
                  </div>
                  <div className="panel-soft p-2.5">
                    <p className="text-[9px] text-[var(--muted-2)]">Duplicates</p>
                    <p className="mono mt-1 text-[16px]">{report?.duplicate_rows?.toLocaleString() ?? '—'}</p>
                  </div>
                </div>
                <p className="mt-3 text-[10px] leading-relaxed text-[var(--muted)]">
                  {result.analyzed ? 'Full pipeline completed and the dashboard data was replaced.' : 'File was validated only; the dashboard was not modified.'}
                </p>
                <pre className="mt-3 max-h-[220px] overflow-auto rounded-lg p-3 text-[9px] leading-relaxed scrollbar-thin" style={{ background: 'var(--ink)', color: 'var(--muted)' }}>
                  {JSON.stringify(result, null, 2)}
                </pre>
              </div>
            </Panel>
          )}

          <Panel title="Safer path for research" eyebrow="Offline ingestion">
            <div className="p-4 text-[10.5px] leading-relaxed text-[var(--muted)]">
              <p>For the real 1.65M corpus, use the reproducible scripts rather than the dashboard uploader:</p>
              <pre className="mono mt-3 whitespace-pre-wrap rounded-lg p-3 text-[9.5px] leading-relaxed" style={{ background: 'var(--ink)' }}>
{`python -m ingestion.real_data
python -m scripts.predict_curated
python -m backend.db.load_real_data`}
              </pre>
              <p className="mt-3 flex items-center gap-1.5 text-[9.5px] text-[var(--muted-2)]">
                <FileSpreadsheet size={11} /> Source hashes and row counts are recorded in the manifest.
              </p>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}
