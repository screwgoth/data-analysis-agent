'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  askQuestion,
  createSession,
  deleteDataset,
  getDataset,
  listDatasets,
  renameDataset,
  type Dataset,
  type DatasetSummary,
  type QueryResult,
} from '@/lib/api'
import { UploadPanel } from '@/components/UploadPanel'
import { ProfileTable } from '@/components/ProfileTable'
import { QuestionBox } from '@/components/QuestionBox'
import { Transcript, type Turn } from '@/components/Transcript'
import { LibrarySidebar } from '@/components/LibrarySidebar'

export default function Home() {
  const [library, setLibrary] = useState<DatasetSummary[]>([])
  const [libLoading, setLibLoading] = useState(true)
  const [libError, setLibError] = useState<string | null>(null)

  // The datasets checked for the next question (multi-select for cross-file).
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  // Full profile of the most-recently-selected dataset (drives ProfileTable).
  const [activeProfile, setActiveProfile] = useState<Dataset | null>(null)

  const [running, setRunning] = useState(false)
  const [turns, setTurns] = useState<Turn[]>([])
  const [askError, setAskError] = useState<string | null>(null)
  // Session id is created lazily on the first question and reused for follow-ups.
  // It is bound to the current dataset selection, so changing the selection
  // resets it.
  const sessionIdRef = useRef<string | null>(null)

  const loadLibrary = useCallback(async () => {
    setLibError(null)
    try {
      const items = await listDatasets()
      setLibrary(items)
      return items
    } catch (e) {
      setLibError(e instanceof Error ? e.message : 'Could not load your dataset library.')
      return null
    } finally {
      setLibLoading(false)
    }
  }, [])

  // Load the persistent library on mount — this is what makes it survive reloads.
  useEffect(() => {
    void loadLibrary()
  }, [loadLibrary])

  // Reset the conversation whenever the active dataset selection changes.
  function resetConversation() {
    setTurns([])
    setAskError(null)
    sessionIdRef.current = null
  }

  async function handleUploaded(d: Dataset) {
    await loadLibrary()
    setSelectedIds([d.id])
    setActiveProfile(d)
    resetConversation()
  }

  async function handleToggleSelect(id: string) {
    const wasSelected = selectedIds.includes(id)
    const next = wasSelected
      ? selectedIds.filter(x => x !== id)
      : [...selectedIds, id]
    setSelectedIds(next)
    resetConversation()

    if (!wasSelected) {
      // Newly selected → show its profile.
      try {
        const full = await getDataset(id)
        setActiveProfile(full)
      } catch {
        // Non-fatal: the row is still selected for querying.
      }
    } else if (activeProfile?.id === id) {
      // Deselected the profiled one → fall back to another selected dataset.
      const fallback = next[next.length - 1]
      if (fallback) {
        try {
          setActiveProfile(await getDataset(fallback))
        } catch {
          setActiveProfile(null)
        }
      } else {
        setActiveProfile(null)
      }
    }
  }

  async function handleRename(id: string, name: string) {
    await renameDataset(id, name)
    await loadLibrary()
    setActiveProfile(prev => (prev && prev.id === id ? { ...prev, name } : prev))
  }

  async function handleDelete(id: string) {
    await deleteDataset(id)
    await loadLibrary()
    setSelectedIds(prev => prev.filter(x => x !== id))
    setActiveProfile(prev => (prev && prev.id === id ? null : prev))
    resetConversation()
  }

  const selectedNames = selectedIds
    .map(id => library.find(d => d.id === id)?.name)
    .filter((n): n is string => Boolean(n))

  const handleAsk = useCallback(
    async (question: string) => {
      if (selectedIds.length === 0 || running) return
      setAskError(null)
      setRunning(true)
      // Optimistically show the question turn immediately.
      setTurns(prev => [...prev, { question, result: null }])

      try {
        // Create/reuse the session so follow-ups resolve against history.
        if (!sessionIdRef.current) {
          sessionIdRef.current = await createSession(selectedIds)
        }
        const result: QueryResult = await askQuestion(
          question,
          selectedIds,
          sessionIdRef.current,
        )
        setTurns(prev => {
          const next = [...prev]
          for (let i = next.length - 1; i >= 0; i--) {
            if (next[i].result === null) {
              next[i] = { ...next[i], result }
              break
            }
          }
          return next
        })
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'The request failed — please try again.'
        setAskError(msg)
        setTurns(prev => {
          const next = [...prev]
          for (let i = next.length - 1; i >= 0; i--) {
            if (next[i].result === null) {
              next.splice(i, 1)
              break
            }
          }
          return next
        })
      } finally {
        setRunning(false)
      }
    },
    [selectedIds, running],
  )

  const hasSelection = selectedIds.length > 0

  return (
    <div className="min-h-screen">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <div>
            <h1 className="text-lg font-bold tracking-tight text-gray-900">
              Local Data Analysis Agent
            </h1>
            <p className="text-xs text-gray-500">
              Upload CSV, Excel, or PDF data, build a persistent library, ask questions across files, and export results — all on your machine.
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 lg:flex-row">
        <LibrarySidebar
          datasets={library}
          selectedIds={selectedIds}
          loading={libLoading}
          error={libError}
          onToggleSelect={handleToggleSelect}
          onRename={handleRename}
          onDelete={handleDelete}
          onRefresh={() => void loadLibrary()}
        />

        <div className="flex min-w-0 flex-1 flex-col gap-6">
          <UploadPanel dataset={activeProfile} onUploaded={d => void handleUploaded(d)} />

          {activeProfile ? (
            <ProfileTable dataset={activeProfile} />
          ) : (
            <section className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center">
              <p className="text-sm text-gray-500">
                Select or upload a dataset to see its column profile — types, ranges, missing values, and PII flags.
              </p>
            </section>
          )}

          {hasSelection && (
            <div
              data-testid="active-datasets"
              className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-2.5 text-xs text-blue-800"
            >
              {selectedNames.length > 1 ? (
                <>
                  Asking across <span className="font-semibold">{selectedNames.length}</span> datasets:{' '}
                  {selectedNames.join(', ')}. The agent proposes a join key or asks a clarifying question if needed.
                </>
              ) : (
                <>
                  Active dataset: <span className="font-semibold">{selectedNames[0]}</span>
                </>
              )}
            </div>
          )}

          <QuestionBox disabled={!hasSelection} running={running} onAsk={handleAsk} />

          {askError && (
            <div
              role="alert"
              className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
            >
              {askError}
            </div>
          )}

          {turns.length > 0 ? (
            <Transcript turns={turns} running={running} onSuggestion={handleAsk} />
          ) : (
            !running &&
            hasSelection && (
              <section className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center">
                <p className="text-sm text-gray-500">
                  Ask a question above to start a conversation. Follow-ups like &ldquo;and just for 2024?&rdquo; resolve against the session, and each answer can be exported as CSV or Excel.
                </p>
              </section>
            )
          )}
        </div>
      </main>
    </div>
  )
}
