'use client'

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ChartSpec } from '@/lib/api'
import type { Row } from '@/lib/records'

const COLORS = ['#2563eb', '#16a34a', '#d97706', '#db2777', '#7c3aed', '#0891b2']

// Interactive chart (bar/line) rendered from the agent's chart_spec, which is
// built from LOCALLY-computed result data. The backend emits categories in
// `spec.x` and values in `spec.series[i].data`, aligned to `x` by index.
// Renders nothing gracefully when the spec is null or carries no plottable data.
export function Chart({ spec }: { spec: ChartSpec | null | undefined }) {
  if (!spec) return null
  const x = Array.isArray(spec.x) ? spec.x : []
  if (x.length === 0) return null

  const series = Array.isArray(spec.series) ? spec.series : []
  const yKeys = series.map(s => s.name)
  if (yKeys.length === 0) return null

  const xKey = spec.x_label || 'x'

  // Zip `x` with each series' `data` by index into one row per category.
  const plotData: Row[] = x.map((label, i) => {
    const row: Row = { [xKey]: label }
    for (const s of series) {
      const raw = Array.isArray(s.data) ? s.data[i] : undefined
      const n = typeof raw === 'number' ? raw : Number(raw)
      row[s.name] = Number.isNaN(n) ? 0 : n
    }
    return row
  })

  const type = (spec.type || 'bar').toLowerCase()
  const isLine = type === 'line' || type === 'area'

  return (
    <div className="mt-4" data-testid="chart">
      <p className="mb-2 text-xs font-medium text-gray-500">
        {spec.title || 'Chart'}
      </p>
      <div className="h-72 w-full rounded-lg border border-gray-200 bg-white p-3">
        <ResponsiveContainer width="100%" height="100%">
          {isLine ? (
            <LineChart data={plotData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey={xKey} tick={{ fontSize: 12 }} label={spec.x_label ? { value: spec.x_label, position: 'insideBottom', offset: -2, fontSize: 11 } : undefined} />
              <YAxis tick={{ fontSize: 12 }} label={spec.y_label ? { value: spec.y_label, angle: -90, position: 'insideLeft', fontSize: 11 } : undefined} />
              <Tooltip />
              {yKeys.length > 1 && <Legend />}
              {yKeys.map((k, i) => (
                <Line key={k} type="monotone" dataKey={k} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={{ r: 3 }} />
              ))}
            </LineChart>
          ) : (
            <BarChart data={plotData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey={xKey} tick={{ fontSize: 12 }} label={spec.x_label ? { value: spec.x_label, position: 'insideBottom', offset: -2, fontSize: 11 } : undefined} />
              <YAxis tick={{ fontSize: 12 }} label={spec.y_label ? { value: spec.y_label, angle: -90, position: 'insideLeft', fontSize: 11 } : undefined} />
              <Tooltip />
              {yKeys.length > 1 && <Legend />}
              {yKeys.map((k, i) => (
                <Bar key={k} dataKey={k} fill={COLORS[i % COLORS.length]} radius={[3, 3, 0, 0]} />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  )
}
