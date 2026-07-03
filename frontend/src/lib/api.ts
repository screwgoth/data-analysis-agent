// API client for the Local Data Analysis Agent.
// Same-origin calls to the FastAPI backend mounted alongside the static export
// (served together at http://localhost:8001/app/). Endpoints live under /api.
//
// Contract: spec/api.md. Responses may or may not be wrapped in the boilerplate
// `ok(...)` envelope ({ data: ... }); `unwrap` tolerates both shapes so the
// frontend integrates whether the backend returns the raw object or the envelope.

export interface ProfileColumn {
  name: string
  dtype: string
  missing_count: number
  likely_pii: boolean
  // Optional numeric-profile fields (present for numeric columns).
  min?: number | null
  max?: number | null
  mean?: number | null
  distinct_count?: number | null
}

export interface Dataset {
  id: string
  name: string
  row_count: number
  col_count: number
  profile: { columns: ProfileColumn[] }
  source_format?: string | null
  created_at?: string | null
}

// Lightweight row returned by GET /api/datasets (the library list). No profile.
export interface DatasetSummary {
  id: string
  name: string
  source_format: string | null
  row_count: number
  col_count: number
  created_at: string | null
}

export interface AnalysisStep {
  step_index: number
  code: string
  stdout: string | null
  result_json: unknown
  error: string | null
  duration_ms: number | null
}

export interface TokenUsage {
  prompt: number
  completion: number
  total: number
  warn: boolean
}

// Chart spec produced by the agent's `build_chart` node from LOCALLY-computed
// result data (raw rows never leave the machine). The exact shape is not pinned
// by spec/api.md beyond "JSON (chart type, data, axes)", so the Chart component
// is deliberately tolerant: `type` picks bar vs line, `x`/`y` name the record
// keys to plot, and `data` is an array of records. Missing/null spec → no chart.
export interface ChartSeries {
  name: string // series label / dataKey
  data: (number | null)[] // values aligned to `x` by index
}

export interface ChartTable {
  columns: string[]
  rows: unknown[][] // positional arrays aligned to `columns`
}

export interface ChartSpec {
  type?: string // "bar" | "line" (default: bar)
  title?: string
  x: string[] // category labels
  x_label?: string
  y_label?: string
  series: ChartSeries[] // each series' data aligned to `x` by index
  table?: ChartTable // summary table (positional rows)
}

export interface QueryResult {
  id: string
  status: string // "completed" | "failed" | ...
  answer: string | null
  assumptions: string[]
  clarifying_question: string | null
  steps: AnalysisStep[]
  chart_spec: ChartSpec | null
  suggestions: string[]
  token_usage: TokenUsage | null
  error_message?: string | null
  // Echoed by the backend so the UI can render turns in order; optional.
  question?: string | null
}

export interface Session {
  id: string
  dataset_ids?: string[]
  // GET /api/sessions/{id} returns ordered prior Query rows as history.
  queries?: QueryResult[]
  history?: QueryResult[]
}

/** Unwrap the optional `{ data: ... }` envelope. */
function unwrap<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in body) {
    const inner = (body as { data: unknown }).data
    if (inner && typeof inner === 'object') return inner as T
  }
  return body as T
}

/** Unwrap a list that may arrive raw (`[...]`) or wrapped (`{ data: [...] }`). */
function unwrapList<T>(body: unknown): T[] {
  if (Array.isArray(body)) return body as T[]
  if (body && typeof body === 'object' && 'data' in body) {
    const inner = (body as { data: unknown }).data
    if (Array.isArray(inner)) return inner as T[]
    // Some list endpoints nest under { data: { datasets: [...] } }.
    if (inner && typeof inner === 'object') {
      for (const v of Object.values(inner as Record<string, unknown>)) {
        if (Array.isArray(v)) return v as T[]
      }
    }
  }
  if (body && typeof body === 'object') {
    for (const v of Object.values(body as Record<string, unknown>)) {
      if (Array.isArray(v)) return v as T[]
    }
  }
  return []
}

/** Pull a human error message out of either error shape. */
function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    const b = body as Record<string, unknown>
    const detail = b.detail
    if (detail && typeof detail === 'object' && 'message' in detail) {
      return String((detail as Record<string, unknown>).message)
    }
    if (typeof detail === 'string') return detail
    if (typeof b.message === 'string') return b.message
    if (typeof b.error === 'string') return b.error
    if (typeof b.error_message === 'string') return b.error_message
  }
  return `Request failed (${status})`
}

export async function uploadDataset(file: File): Promise<Dataset> {
  const form = new FormData()
  form.append('file', file)
  form.append('name', file.name)
  const res = await fetch('/api/datasets', { method: 'POST', body: form })
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // fall through to status-based error below
  }
  if (!res.ok) throw new Error(errorMessage(body, res.status))
  return unwrap<Dataset>(body)
}

function normalizeResult(r: QueryResult): QueryResult {
  // The contract promises arrays; guard against null so the UI never crashes
  // if the backend omits an optional list.
  return {
    ...r,
    assumptions: r.assumptions ?? [],
    steps: r.steps ?? [],
    suggestions: r.suggestions ?? [],
  }
}

/** Create a session over the given dataset(s). Returns its session_id. */
export async function createSession(datasetIds: string[]): Promise<string> {
  const res = await fetch('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_ids: datasetIds }),
  })
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // fall through
  }
  if (!res.ok) throw new Error(errorMessage(body, res.status))
  return unwrap<Session>(body).id
}

/** Fetch a session's ordered history (used to restore a transcript). */
export async function getSession(sessionId: string): Promise<Session> {
  const res = await fetch(`/api/sessions/${sessionId}`)
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // fall through
  }
  if (!res.ok) throw new Error(errorMessage(body, res.status))
  return unwrap<Session>(body)
}

/** List every dataset in the persistent library (GET /api/datasets). */
export async function listDatasets(): Promise<DatasetSummary[]> {
  const res = await fetch('/api/datasets')
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // fall through
  }
  if (!res.ok) throw new Error(errorMessage(body, res.status))
  return unwrapList<DatasetSummary>(body)
}

/** Fetch one dataset with its full profile (GET /api/datasets/{id}). */
export async function getDataset(id: string): Promise<Dataset> {
  const res = await fetch(`/api/datasets/${id}`)
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // fall through
  }
  if (!res.ok) throw new Error(errorMessage(body, res.status))
  return unwrap<Dataset>(body)
}

/** Rename a dataset (PATCH /api/datasets/{id}). Returns the updated summary. */
export async function renameDataset(id: string, name: string): Promise<DatasetSummary> {
  const res = await fetch(`/api/datasets/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // fall through
  }
  if (!res.ok) throw new Error(errorMessage(body, res.status))
  return unwrap<DatasetSummary>(body)
}

/** Delete a dataset and its local file (DELETE /api/datasets/{id}). */
export async function deleteDataset(id: string): Promise<void> {
  const res = await fetch(`/api/datasets/${id}`, { method: 'DELETE' })
  if (!res.ok) {
    let body: unknown = null
    try {
      body = await res.json()
    } catch {
      // fall through
    }
    throw new Error(errorMessage(body, res.status))
  }
}

/**
 * Build the same-origin download URL for a query's exported result.
 * Served under /api (NOT the /app basePath), so an absolute-from-root path
 * resolves correctly whether the app is at /app/ or elsewhere.
 */
export function exportUrl(queryId: string, format: 'csv' | 'xlsx'): string {
  return `/api/queries/${queryId}/export?format=${format}`
}

export async function askQuestion(
  question: string,
  datasetIds: string[],
  sessionId: string | null = null,
): Promise<QueryResult> {
  const res = await fetch('/api/queries', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      dataset_ids: datasetIds,
      session_id: sessionId,
    }),
  })
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // fall through
  }
  if (!res.ok) throw new Error(errorMessage(body, res.status))
  return normalizeResult(unwrap<QueryResult>(body))
}
