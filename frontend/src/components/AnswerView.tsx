'use client'

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { AnalysisStep, QueryResult } from '@/lib/api'
import { recordsFromResult } from '@/lib/records'
import { Chart } from './Chart'
import { SummaryTable } from './SummaryTable'
import { Suggestions } from './Suggestions'
import { TokenBadge } from './TokenBadge'
import { ExportMenu } from './ExportMenu'

function StepCard({ step }: { step: AnalysisStep }) {
  const hasResult =
    step.result_json !== null &&
    step.result_json !== undefined &&
    !(typeof step.result_json === 'object' && Object.keys(step.result_json).length === 0)

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-500">Step {step.step_index + 1}</span>
        {typeof step.duration_ms === 'number' && (
          <span className="text-xs text-gray-400">{step.duration_ms} ms</span>
        )}
      </div>
      <pre
        data-testid="step-code"
        className="overflow-x-auto rounded-md bg-gray-900 p-3 text-xs leading-relaxed text-gray-100"
      >
        <code>{step.code}</code>
      </pre>

      {step.stdout && step.stdout.trim() && (
        <div className="mt-2">
          <p className="mb-1 text-xs font-medium text-gray-500">Output</p>
          <pre className="overflow-x-auto rounded-md bg-gray-50 p-2 text-xs text-gray-700">
            {step.stdout}
          </pre>
        </div>
      )}

      {hasResult && (
        <div className="mt-2">
          <p className="mb-1 text-xs font-medium text-gray-500">Result</p>
          <pre className="overflow-x-auto rounded-md bg-gray-50 p-2 text-xs text-gray-700">
            {JSON.stringify(step.result_json, null, 2)}
          </pre>
        </div>
      )}

      {step.error && (
        <div className="mt-2 rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700">
          <span className="font-medium">Error:</span> {step.error}
        </div>
      )}
    </div>
  )
}

/**
 * Renders a single completed turn's answer: prose + assumptions + collapsible
 * code + interactive chart + sortable summary table + follow-up suggestions +
 * token badge. Also handles the clarifying-question and failed states.
 *
 * `onSuggestion` submits a suggestion (or the reply to a clarifying question)
 * as the next turn in the same session. `busy` disables interaction while a
 * later turn is already running.
 */
export function AnswerView({
  result,
  onSuggestion,
  busy,
}: {
  result: QueryResult
  onSuggestion?: (question: string) => void
  busy?: boolean
}) {
  const [showCode, setShowCode] = useState(false)

  const failed = result.status === 'failed' || result.status === 'error'

  if (failed) {
    return (
      <section
        role="alert"
        className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700 shadow-sm"
      >
        <h3 className="mb-1 text-base font-semibold text-red-800">Analysis failed</h3>
        <p>
          {result.error_message?.trim() ||
            'The agent could not complete this analysis. Try rephrasing the question.'}
        </p>
        {result.steps.length > 0 && (
          <details className="mt-3">
            <summary className="cursor-pointer text-xs font-medium text-red-700">
              Show attempted steps
            </summary>
            <div className="mt-2 space-y-2">
              {result.steps.map(s => (
                <StepCard key={s.step_index} step={s} />
              ))}
            </div>
          </details>
        )}
      </section>
    )
  }

  // Clarifying-question state: the agent is asking the user, NOT an error.
  // Render distinctly and let the user answer as the next turn.
  const clarifying = result.clarifying_question?.trim()

  const lastStepResult = result.steps.length > 0 ? result.steps[result.steps.length - 1].result_json : undefined
  const tableRows = recordsFromResult(result.chart_spec?.table, lastStepResult)

  return (
    <div className="space-y-3">
      {clarifying && (
        <div
          data-testid="clarifying-question"
          className="rounded-lg border border-indigo-200 bg-indigo-50 p-4"
        >
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-indigo-500">
            The agent needs a bit more detail
          </p>
          <p className="text-sm text-indigo-900">{clarifying}</p>
          {onSuggestion && (
            <p className="mt-2 text-xs text-indigo-600">
              Type your answer in the question box below to continue.
            </p>
          )}
        </div>
      )}

      {result.assumptions.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <p className="mb-1 font-medium">Assumptions</p>
          <ul className="list-inside list-disc space-y-0.5">
            {result.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      {(result.answer?.trim() || !clarifying) && (
        <div
          data-testid="answer-prose"
          className="prose prose-sm max-w-none text-gray-800 [&_code]:rounded [&_code]:bg-gray-100 [&_code]:px-1 [&_table]:w-full [&_th]:text-left"
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {result.answer?.trim() || '_No answer text was returned._'}
          </ReactMarkdown>
        </div>
      )}

      <Chart spec={result.chart_spec} />
      <SummaryTable rows={tableRows} />

      {result.steps.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setShowCode(v => !v)}
            aria-expanded={showCode}
            data-testid="show-code-toggle"
            className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-gray-50 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100"
          >
            <span aria-hidden="true">{showCode ? '▾' : '▸'}</span>
            {showCode ? 'Hide code' : `Show code (${result.steps.length} step${result.steps.length === 1 ? '' : 's'})`}
          </button>

          {showCode && (
            <div data-testid="code-trace" className="mt-3 space-y-3">
              {result.steps.map(s => (
                <StepCard key={s.step_index} step={s} />
              ))}
            </div>
          )}
        </div>
      )}

      {onSuggestion && (
        <Suggestions suggestions={result.suggestions} onPick={onSuggestion} disabled={busy} />
      )}

      {/* Export is available once the query produced a real result (has code
          steps), and never for a pure clarifying-question turn. */}
      {!clarifying && result.steps.length > 0 && <ExportMenu queryId={result.id} />}

      {result.token_usage && (
        <div className="flex items-center gap-2 border-t border-gray-100 pt-3">
          <TokenBadge usage={result.token_usage} />
        </div>
      )}
    </div>
  )
}
