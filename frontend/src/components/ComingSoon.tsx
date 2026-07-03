// A clearly-labelled, intentionally non-functional stub for a feature that
// ships in a later phase. Must never look like a bug: muted styling + an
// explicit "Coming soon" badge naming the phase.

export function ComingSoonBadge({ phase }: { phase: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-500">
      Coming soon · {phase}
    </span>
  )
}

export function ComingSoon({
  title,
  description,
  phase,
  action,
}: {
  title: string
  description: string
  phase: string
  action?: string
}) {
  return (
    <section
      aria-disabled="true"
      data-testid={`stub-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
      className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4 opacity-80"
    >
      <div className="mb-1 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-500">{title}</h3>
        <ComingSoonBadge phase={phase} />
      </div>
      <p className="text-xs text-gray-400">{description}</p>
      {action && (
        <button
          type="button"
          disabled
          className="mt-3 cursor-not-allowed rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-400"
        >
          {action}
        </button>
      )}
    </section>
  )
}
