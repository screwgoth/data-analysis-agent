'use client'

import { useState } from 'react'
import { Spinner } from './Spinner'

export function QuestionBox({
  disabled,
  running,
  onAsk,
}: {
  disabled: boolean
  running: boolean
  onAsk: (question: string) => void
}) {
  const [question, setQuestion] = useState('')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q || running || disabled) return
    onAsk(q)
  }

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-base font-semibold text-gray-900">3 · Ask a question</h2>

      {disabled ? (
        <p className="text-sm text-gray-400">Upload a dataset first to ask a question.</p>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <label htmlFor="question" className="sr-only">
            Your question about the data
          </label>
          <textarea
            id="question"
            rows={2}
            value={question}
            onChange={e => setQuestion(e.target.value)}
            disabled={running}
            placeholder="e.g. What is the total revenue by region?"
            className="w-full rounded-lg border border-gray-300 p-3 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-60"
            onKeyDown={e => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit(e)
            }}
          />
          <div className="flex items-center justify-between gap-3">
            <button
              type="submit"
              disabled={running || !question.trim()}
              className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {running ? 'Analyzing…' : 'Ask'}
            </button>
            {running && <Spinner label="Analyzing — writing and running pandas locally…" />}
          </div>
        </form>
      )}
    </section>
  )
}
