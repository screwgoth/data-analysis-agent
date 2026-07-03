'use client'

import { useState } from 'react'
import type { DatasetSummary } from '@/lib/api'

const FORMAT_STYLES: Record<string, string> = {
  csv: 'bg-emerald-100 text-emerald-700',
  xlsx: 'bg-indigo-100 text-indigo-700',
  xls: 'bg-indigo-100 text-indigo-700',
  pdf: 'bg-rose-100 text-rose-700',
}

function FormatBadge({ format }: { format: string | null }) {
  const key = (format ?? '').toLowerCase().replace(/^\./, '')
  const label = key ? key.toUpperCase() : 'FILE'
  const style = FORMAT_STYLES[key] ?? 'bg-gray-100 text-gray-600'
  return (
    <span
      data-testid="format-badge"
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${style}`}
    >
      {label}
    </span>
  )
}

/**
 * Persistent dataset library. Reads its rows from the backend (GET /api/datasets)
 * so the list survives reloads. Supports:
 *  - multi-select (checkbox) → datasets included in the next question
 *  - inline rename (PATCH)
 *  - delete with confirmation (DELETE)
 * Clicking a row selects it (and loads its profile via the parent).
 */
export function LibrarySidebar({
  datasets,
  selectedIds,
  loading,
  error,
  onToggleSelect,
  onRename,
  onDelete,
  onRefresh,
}: {
  datasets: DatasetSummary[]
  selectedIds: string[]
  loading: boolean
  error: string | null
  onToggleSelect: (id: string) => void
  onRename: (id: string, name: string) => Promise<void>
  onDelete: (id: string) => Promise<void>
  onRefresh: () => void
}) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draftName, setDraftName] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)

  function startEdit(d: DatasetSummary) {
    setEditingId(d.id)
    setDraftName(d.name)
  }

  async function commitEdit(id: string) {
    const name = draftName.trim()
    setEditingId(null)
    if (!name) return
    const current = datasets.find(d => d.id === id)
    if (current && current.name === name) return
    setBusyId(id)
    try {
      await onRename(id, name)
    } finally {
      setBusyId(null)
    }
  }

  async function confirmDelete(d: DatasetSummary) {
    if (!window.confirm(`Delete "${d.name}"? This removes the dataset and its local file.`)) {
      return
    }
    setBusyId(d.id)
    try {
      await onDelete(d.id)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <aside className="flex w-full shrink-0 flex-col gap-3 lg:w-72">
      <section className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900">Dataset library</h2>
          <button
            type="button"
            onClick={onRefresh}
            className="rounded-md border border-gray-200 px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50"
          >
            Refresh
          </button>
        </div>

        {selectedIds.length > 1 && (
          <p
            data-testid="multiselect-hint"
            className="mb-3 rounded-md bg-blue-50 px-2 py-1.5 text-xs text-blue-700"
          >
            {selectedIds.length} datasets selected — your next question runs across all of them.
          </p>
        )}

        {loading && (
          <p className="py-6 text-center text-xs text-gray-400" role="status">
            Loading your library…
          </p>
        )}

        {error && !loading && (
          <div
            role="alert"
            className="rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700"
          >
            {error}
          </div>
        )}

        {!loading && !error && datasets.length === 0 && (
          <p
            data-testid="library-empty"
            className="rounded-lg border border-dashed border-gray-300 bg-gray-50 px-3 py-6 text-center text-xs text-gray-500"
          >
            No datasets yet. Upload a CSV, Excel, or PDF file to start your library — it persists across sessions.
          </p>
        )}

        {!loading && datasets.length > 0 && (
          <ul data-testid="library-list" className="flex flex-col gap-2">
            {datasets.map(d => {
              const selected = selectedIds.includes(d.id)
              const busy = busyId === d.id
              return (
                <li
                  key={d.id}
                  data-testid="library-item"
                  className={`rounded-lg border p-2.5 transition-colors ${
                    selected ? 'border-blue-400 bg-blue-50' : 'border-gray-200 bg-white hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      checked={selected}
                      aria-label={`Select ${d.name}`}
                      onChange={() => onToggleSelect(d.id)}
                      className="mt-0.5 h-4 w-4 shrink-0 rounded border-gray-300 text-blue-600"
                    />
                    <div className="min-w-0 flex-1">
                      {editingId === d.id ? (
                        <input
                          autoFocus
                          value={draftName}
                          onChange={e => setDraftName(e.target.value)}
                          onBlur={() => void commitEdit(d.id)}
                          onKeyDown={e => {
                            if (e.key === 'Enter') void commitEdit(d.id)
                            if (e.key === 'Escape') setEditingId(null)
                          }}
                          data-testid="rename-input"
                          className="w-full rounded border border-blue-300 px-1.5 py-0.5 text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        />
                      ) : (
                        <button
                          type="button"
                          onClick={() => onToggleSelect(d.id)}
                          data-testid="library-item-name"
                          title={d.name}
                          className="block w-full truncate text-left text-sm font-medium text-gray-900"
                        >
                          {d.name}
                        </button>
                      )}
                      <div className="mt-1 flex items-center gap-2">
                        <FormatBadge format={d.source_format} />
                        <span className="text-[11px] text-gray-500">
                          {d.row_count.toLocaleString()} × {d.col_count.toLocaleString()}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-2 flex items-center gap-3 pl-6">
                    <button
                      type="button"
                      onClick={() => startEdit(d)}
                      disabled={busy}
                      data-testid="rename-button"
                      className="text-[11px] font-medium text-gray-500 hover:text-blue-600 disabled:opacity-50"
                    >
                      Rename
                    </button>
                    <button
                      type="button"
                      onClick={() => void confirmDelete(d)}
                      disabled={busy}
                      data-testid="delete-button"
                      className="text-[11px] font-medium text-gray-500 hover:text-red-600 disabled:opacity-50"
                    >
                      Delete
                    </button>
                    {busy && <span className="text-[11px] text-gray-400">…</span>}
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </aside>
  )
}
