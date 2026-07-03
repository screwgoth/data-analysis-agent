'use client'

import type { QueryResult } from '@/lib/api'
import { AnswerView } from './AnswerView'
import { Spinner } from './Spinner'

export interface Turn {
  question: string
  result: QueryResult | null // null while this turn is still running
}

// Chat-style transcript: every prior turn stays visible (question bubble +
// its full answer). The most recent turn may still be running (spinner).
export function Transcript({
  turns,
  running,
  onSuggestion,
}: {
  turns: Turn[]
  running: boolean
  onSuggestion: (question: string) => void
}) {
  if (turns.length === 0) return null

  return (
    <section
      data-testid="transcript"
      className="flex flex-col gap-5 rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
    >
      <h2 className="text-base font-semibold text-gray-900">Conversation</h2>

      {turns.map((turn, i) => {
        const isLast = i === turns.length - 1
        return (
          <div key={i} data-testid="turn" className="flex flex-col gap-3">
            <div className="flex justify-end">
              <div
                data-testid="turn-question"
                className="max-w-[85%] rounded-2xl rounded-br-sm bg-blue-600 px-4 py-2 text-sm text-white"
              >
                {turn.question}
              </div>
            </div>

            {turn.result ? (
              <div className="flex justify-start">
                <div className="w-full max-w-[95%] rounded-2xl rounded-bl-sm border border-gray-100 bg-gray-50 p-4">
                  <AnswerView
                    result={turn.result}
                    onSuggestion={onSuggestion}
                    busy={running}
                  />
                </div>
              </div>
            ) : (
              isLast &&
              running && (
                <div className="flex justify-start">
                  <div className="rounded-2xl rounded-bl-sm border border-gray-100 bg-gray-50 px-4 py-3">
                    <Spinner label="Analyzing — writing and running pandas locally…" />
                  </div>
                </div>
              )
            )}
          </div>
        )
      })}
    </section>
  )
}
