'use client'

import { useState } from 'react'
import { askQuestion, type Dataset, type QueryResult } from '@/lib/api'
import { UploadPanel } from '@/components/UploadPanel'
import { ProfileTable } from '@/components/ProfileTable'
import { QuestionBox } from '@/components/QuestionBox'
import { AnswerView } from '@/components/AnswerView'
import { Sidebar } from '@/components/Sidebar'

export default function Home() {
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<QueryResult | null>(null)
  const [askError, setAskError] = useState<string | null>(null)

  function handleUploaded(d: Dataset) {
    setDataset(d)
    setResult(null)
    setAskError(null)
  }

  async function handleAsk(question: string) {
    if (!dataset) return
    setRunning(true)
    setAskError(null)
    setResult(null)
    try {
      const r = await askQuestion(question, [dataset.id])
      setResult(r)
    } catch (e) {
      setAskError(e instanceof Error ? e.message : 'The request failed — please try again.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <div>
            <h1 className="text-lg font-bold tracking-tight text-gray-900">
              Local Data Analysis Agent
            </h1>
            <p className="text-xs text-gray-500">
              Upload a CSV, ask a question, and see the exact pandas the agent ran — all on your machine.
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

          {result ? (
            <AnswerView result={result} />
          ) : (
            !running &&
            dataset && (
              <section className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center">
                <p className="text-sm text-gray-500">
                  Ask a question above to get a prose answer with the key numbers and the code behind it.
                </p>
              </section>
            )
          )}
        </div>
      </main>
    </div>
  )
}
