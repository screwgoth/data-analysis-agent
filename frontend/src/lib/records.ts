// Helpers to coerce loosely-typed result payloads into a rectangular set of
// records the SummaryTable/Chart can render. The backend's chart_spec.table
// ({columns, rows}) is the primary source; when absent we fall back to the last
// analysis step's result_json. Raw data never leaves the machine — these are
// already the locally-computed, aggregated results the user sees.

import type { ChartTable } from '@/lib/api'

export type Row = Record<string, unknown>

/** True when `v` is an array of plain objects (records). */
function isRecordArray(v: unknown): v is Row[] {
  return (
    Array.isArray(v) &&
    v.length > 0 &&
    v.every(el => el !== null && typeof el === 'object' && !Array.isArray(el))
  )
}

/**
 * Coerce an arbitrary result value into an array of records.
 * Handles:
 *  - already an array of records  → as-is
 *  - dict-of-dicts (pandas .to_dict())  → rows keyed by index
 *  - dict-of-scalars (a single Series / groupby result)  → [{key, value}]
 * Returns [] for anything non-tabular.
 */
export function toRecords(value: unknown): Row[] {
  if (value == null) return []
  if (isRecordArray(value)) return value

  if (typeof value === 'object' && !Array.isArray(value)) {
    const obj = value as Row
    const entries = Object.entries(obj)
    if (entries.length === 0) return []

    // dict-of-dicts: { "0": {a:1}, "1": {a:2} }
    if (entries.every(([, v]) => v !== null && typeof v === 'object' && !Array.isArray(v))) {
      return entries.map(([k, v]) => ({ index: k, ...(v as Row) }))
    }

    // dict-of-scalars: { "North": 1200, "South": 640 }
    if (entries.every(([, v]) => v === null || typeof v !== 'object')) {
      return entries.map(([k, v]) => ({ key: k, value: v }))
    }
  }
  return []
}

/** Ordered, de-duplicated column keys across all records. */
export function recordColumns(rows: Row[]): string[] {
  const cols: string[] = []
  for (const r of rows) {
    for (const k of Object.keys(r)) if (!cols.includes(k)) cols.push(k)
  }
  return cols
}

/**
 * Convert a chart_spec.table ({columns, rows}) — where each row is a POSITIONAL
 * array aligned to `columns` — into an array of records keyed by column name.
 * Column order is preserved via object insertion order.
 */
export function recordsFromTable(table: ChartTable | null | undefined): Row[] {
  if (!table || !Array.isArray(table.columns) || !Array.isArray(table.rows)) return []
  const { columns, rows } = table
  if (columns.length === 0) return []
  return rows.map(row => {
    const rec: Row = {}
    const cells = Array.isArray(row) ? row : []
    columns.forEach((col, i) => {
      rec[col] = cells[i]
    })
    return rec
  })
}

/**
 * Best-effort records for a summary table. Prefers the backend's
 * chart_spec.table (positional {columns, rows}); falls back to the last
 * analysis step's result_json when no table is present.
 */
export function recordsFromResult(table?: ChartTable | null, lastStepResult?: unknown): Row[] {
  const fromTable = recordsFromTable(table)
  if (fromTable.length > 0) return fromTable
  return toRecords(lastStepResult)
}
