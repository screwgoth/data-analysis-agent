'use client'

// 2–3 follow-up suggestions rendered as clickable chips. Clicking one submits
// it as the next question in the same session.
export function Suggestions({
  suggestions,
  onPick,
  disabled,
}: {
  suggestions: string[]
  onPick: (question: string) => void
  disabled?: boolean
}) {
  if (!suggestions || suggestions.length === 0) return null

  return (
    <div className="mt-4" data-testid="suggestions">
      <p className="mb-2 text-xs font-medium text-gray-500">Follow-up suggestions</p>
      <div className="flex flex-wrap gap-2">
        {suggestions.map((s, i) => (
          <button
            key={i}
            type="button"
            disabled={disabled}
            data-testid="suggestion-chip"
            onClick={() => onPick(s)}
            className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 transition-colors hover:border-blue-300 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}
