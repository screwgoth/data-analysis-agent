import type { Dataset, ProfileColumn } from '@/lib/api'

function formatNum(n: number): string {
  if (!Number.isFinite(n)) return String(n)
  if (Number.isInteger(n)) return n.toLocaleString()
  return n.toLocaleString(undefined, { maximumFractionDigits: 4 })
}

function rangeText(c: ProfileColumn): string {
  const has = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
  if (has(c.min) && has(c.max)) return `${formatNum(c.min)} – ${formatNum(c.max)}`
  if (has(c.min)) return `≥ ${formatNum(c.min)}`
  if (has(c.max)) return `≤ ${formatNum(c.max)}`
  return '—'
}

export function ProfileTable({ dataset }: { dataset: Dataset }) {
  const columns = dataset.profile?.columns ?? []

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold text-gray-900">2 · Profile</h2>
        <p className="text-xs text-gray-500">
          {dataset.row_count.toLocaleString()} rows · {dataset.col_count.toLocaleString()} columns
        </p>
      </div>

      {columns.length === 0 ? (
        <p className="text-sm text-gray-400">No columns were profiled for this file.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
                <th className="py-2 pr-4 font-medium">Column</th>
                <th className="py-2 pr-4 font-medium">Type</th>
                <th className="py-2 pr-4 font-medium">Missing</th>
                <th className="py-2 pr-4 font-medium">Range</th>
                <th className="py-2 pr-4 font-medium">Flags</th>
              </tr>
            </thead>
            <tbody>
              {columns.map(c => (
                <tr key={c.name} className="border-b border-gray-100 last:border-0">
                  <td className="py-2 pr-4 font-medium text-gray-900">{c.name}</td>
                  <td className="py-2 pr-4">
                    <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700">
                      {c.dtype}
                    </code>
                  </td>
                  <td className="py-2 pr-4 text-gray-700">
                    {c.missing_count > 0 ? (
                      <span className="text-amber-700">{c.missing_count.toLocaleString()}</span>
                    ) : (
                      <span className="text-gray-400">0</span>
                    )}
                  </td>
                  <td className="py-2 pr-4 text-gray-700">{rangeText(c)}</td>
                  <td className="py-2 pr-4">
                    {c.likely_pii ? (
                      <span
                        data-testid="pii-badge"
                        title="Values matching PII heuristics are masked before anything is sent to the model."
                        className="inline-flex items-center rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-700"
                      >
                        PII · masked
                      </span>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
