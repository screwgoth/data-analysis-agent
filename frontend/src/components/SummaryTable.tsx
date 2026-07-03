'use client'

import { useMemo, useState } from 'react'
import { recordColumns, type Row } from '@/lib/records'

function formatCell(v: unknown): string {
  if (v == null) return '—'
  if (typeof v === 'number') {
    return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 4 })
  }
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

function compare(a: unknown, b: unknown): number {
  const an = typeof a === 'number' ? a : Number(a)
  const bn = typeof b === 'number' ? b : Number(b)
  if (!Number.isNaN(an) && !Number.isNaN(bn)) return an - bn
  return String(a ?? '').localeCompare(String(b ?? ''))
}

// Sortable summary table built from LOCALLY-computed result records. Click a
// column header to sort; click again to reverse.
export function SummaryTable({ rows }: { rows: Row[] }) {
  const columns = useMemo(() => recordColumns(rows), [rows])
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [dir, setDir] = useState<'asc' | 'desc'>('asc')

  const sorted = useMemo(() => {
    if (!sortKey) return rows
    const copy = [...rows]
    copy.sort((r1, r2) => {
      const c = compare(r1[sortKey], r2[sortKey])
      return dir === 'asc' ? c : -c
    })
    return copy
  }, [rows, sortKey, dir])

  if (rows.length === 0 || columns.length === 0) return null

  function onHeaderClick(key: string) {
    if (sortKey === key) {
      setDir(d => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setDir('asc')
    }
  }

  return (
    <div className="mt-4" data-testid="summary-table">
      <p className="mb-2 text-xs font-medium text-gray-500">Summary table</p>
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
              {columns.map(col => (
                <th key={col} className="px-3 py-2 font-medium">
                  <button
                    type="button"
                    data-testid="sort-header"
                    onClick={() => onHeaderClick(col)}
                    className="inline-flex items-center gap-1 hover:text-gray-800"
                  >
                    {col}
                    <span aria-hidden="true" className="text-gray-400">
                      {sortKey === col ? (dir === 'asc' ? '▲' : '▼') : '↕'}
                    </span>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((r, i) => (
              <tr key={i} className="border-b border-gray-100 last:border-0">
                {columns.map(col => (
                  <td key={col} className="px-3 py-2 text-gray-700">
                    {formatCell(r[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
