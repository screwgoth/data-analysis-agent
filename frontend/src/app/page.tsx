'use client'

import { useCallback, useRef, useState } from 'react'
import {
  askQuestion,
  createSession,
  type Dataset,
  type QueryResult,
} from '@/lib/api'
import { UploadPanel } from '@/components/UploadPanel'
import { ProfileTable } from '@/components/ProfileTable'
import { QuestionBox } from '@/components/QuestionBox'
import { Transcript, type Turn } from '@/components/Transcript'
import { Sidebar } from '@/components/Sidebar'

export default function Home() {
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [running, setRunning] = useState(false)
  const [turns, setTurns] = useState<Turn[]>([])
  const [askError, setAskError] = useState<string | null>(null)
  // Session id is created lazily on the first question and reused for follow-ups.
  const sessionIdRef = useRef<string | null>(null)

  function handleUploaded(d: Dataset) {
    setDataset(d)
    setTurns([])
    setAskError(null)
    sessionIdRef.current = null
  }

  const handleAsk = useCallback(
    async (question: string) => {
      if (!dataset || running) return
      setAskError(null)
      setRunning(true)
      // Optimistically show the question turn immediately.
      setTurns(prev => [...prev, { question, result: null }])

      try {
        // Create/reuse the session so follow-ups resolve against history.
        if (!sessionIdRef.current) {
          sessionIdRef.current = await createSession([dataset.id])
        }
        const result: QueryResult = await askQuestion(
          question,
          [dataset.id],
          sessionIdRef.current,
        )
        setTurns(prev => {
          const next = [...prev]
          // Attach the result to the last (pending) turn.
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
        // Drop the pending turn so the transcript never shows a stuck bubble.
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
    [dataset, running],
  )

  return (
    <div className="min-h-screen">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <div>
            <h1 className="text-lg font-bold tracking-tight text-gray-900">
              Local Data Analysis Agent
            </h1>
            <p className="text-xs text-gray-500">
              Upload a CSV, ask questions in a session, and see the exact pandas the agent ran — all on your machine.
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 lg:flex-row">
        <Sidebar />

        <div className="flex min-w-0 flex-1 flex-col gap-6">
          <UploadPanel dataset={dataset} onUploaded={handleUploaded} />

          {dataset ? (
            <ProfileTable dataset={dataset} />
          ) : (
            <section className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center">
              <p className="text-sm text-gray-500">
                Your dataset&apos;s column profile — types, ranges, missing values, and PII flags — appears here after upload.
              </p>
            </section>
          )}

          <QuestionBox disabled={!dataset} running={running} onAsk={handleAsk} />

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
            dataset && (
              <section className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center">
                <p className="text-sm text-gray-500">
                  Ask a question above to start a conversation. Follow-ups like &ldquo;and just for 2024?&rdquo; resolve against the session, and each answer suggests what to ask next.
                </p>
              </section>
            )
          )}
        </div>
      </main>
    </div>
  )
}
