import type { TokenUsage } from '@/lib/api'

// Per-query token count. Dollar cost is NEVER shown (spec: token counts only).
// When `warn` is true the badge switches to a high-spend warning style so an
// unusually expensive query is obvious at a glance.
export function TokenBadge({ usage }: { usage: TokenUsage | null }) {
  if (!usage || typeof usage.total !== 'number') return null

  const warn = usage.warn === true
  const total = usage.total.toLocaleString()

  return (
    <span
      data-testid="token-badge"
      data-warn={warn ? 'true' : 'false'}
      title={`Prompt ${usage.prompt?.toLocaleString() ?? '—'} · Completion ${
        usage.completion?.toLocaleString() ?? '—'
      } tokens`}
      className={
        warn
          ? 'inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800'
          : 'inline-flex items-center gap-1 rounded-full border border-gray-200 bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600'
      }
    >
      {warn && (
        <span aria-hidden="true" title="High token spend">
          ⚠
        </span>
      )}
      <span>{total} tokens</span>
      {warn && <span className="font-bold uppercase tracking-wide">High spend</span>}
    </span>
  )
}
