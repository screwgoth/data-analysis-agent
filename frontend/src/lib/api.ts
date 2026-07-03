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

export interface QueryResult {
  id: string
  status: string // "completed" | "failed" | ...
  answer: string | null
  assumptions: string[]
  clarifying_question: string | null
  steps: AnalysisStep[]
  chart_spec: unknown | null
  suggestions: string[]
  token_usage: TokenUsage | null
  error_message?: string | null
}

/** Unwrap the optional `{ data: ... }` envelope. */
function unwrap<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in body) {
    const inner = (body as { data: unknown }).data
    if (inner && typeof inner === 'object') return inner as T
  }
  return body as T
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

export async function askQuestion(
  question: string,
  datasetIds: string[],
): Promise<QueryResult> {
  const res = await fetch('/api/queries', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      dataset_ids: datasetIds,
      session_id: null,
    }),
  })
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // fall through
  }
  if (!res.ok) throw new Error(errorMessage(body, res.status))
  const r = unwrap<QueryResult>(body)
  // Normalize: the contract promises arrays, but guard against null so the UI
  // never crashes if the backend omits an optional list.
  return {
    ...r,
    assumptions: r.assumptions ?? [],
    steps: r.steps ?? [],
    suggestions: r.suggestions ?? [],
  }
}
