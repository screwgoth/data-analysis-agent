import { ComingSoon } from './ComingSoon'

export function Sidebar() {
  return (
    <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-64">
      <ComingSoon
        title="Dataset library"
        description="Save, rename, select, and delete datasets across sessions. For now, one CSV at a time."
        phase="Phase 3"
        action="+ New dataset"
      />
      <ComingSoon
        title="Multi-file join"
        description="Select multiple datasets and join them on a proposed key to analyze across files."
        phase="Phase 3"
      />
      <ComingSoon
        title="Export"
        description="Download cleaned data or a result as CSV / XLSX."
        phase="Phase 3"
        action="Export result"
      />
    </aside>
  )
}
