'use client'

import { exportUrl } from '@/lib/api'

/**
 * Export control for a completed query's result. Renders real download links
 * (GET /api/queries/{id}/export?format=csv|xlsx). Uses anchor `download` so the
 * browser initiates a genuine file download rather than navigating away.
 */
export function ExportMenu({ queryId }: { queryId: string }) {
  return (
    <div
      data-testid="export-menu"
      className="flex items-center gap-2 border-t border-gray-100 pt-3"
    >
      <span className="text-xs font-medium text-gray-500">Export result:</span>
      <a
        href={exportUrl(queryId, 'csv')}
        download
        data-testid="export-csv"
        className="inline-flex items-center rounded-md border border-gray-300 bg-white px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
      >
        CSV
      </a>
      <a
        href={exportUrl(queryId, 'xlsx')}
        download
        data-testid="export-xlsx"
        className="inline-flex items-center rounded-md border border-gray-300 bg-white px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
      >
        Excel
      </a>
    </div>
  )
}
