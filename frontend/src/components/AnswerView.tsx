'use client'

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { AnalysisStep, QueryResult } from '@/lib/api'
import { ComingSoonBadge } from './ComingSoon'

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

export function AnswerView({ result }: { result: QueryResult }) {
  const [showCode, setShowCode] = useState(false)

  const failed = result.status === 'failed' || result.status === 'error'

  if (failed) {
    return (
      <section
        role="alert"
        className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700 shadow-sm"
      >
        <h2 className="mb-1 text-base font-semibold text-red-800">Analysis failed</h2>
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

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-base font-semibold text-gray-900">4 · Answer</h2>

      {result.assumptions.length > 0 && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <p className="mb-1 font-medium">Assumptions</p>
          <ul className="list-inside list-disc space-y-0.5">
            {result.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      <div
        data-testid="answer-prose"
        className="prose prose-sm max-w-none text-gray-800 [&_code]:rounded [&_code]:bg-gray-100 [&_code]:px-1 [&_table]:w-full [&_th]:text-left"
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {result.answer?.trim() || '_No answer text was returned._'}
        </ReactMarkdown>
      </div>

      {result.steps.length > 0 && (
        <div className="mt-4">
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

      {/* Phase 2 stubs, inline under the answer so their place is obvious. */}
      <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-gray-100 pt-4">
        <span className="inline-flex items-center gap-2 text-xs text-gray-400">
          Chart <ComingSoonBadge phase="Phase 2" />
        </span>
        <span className="inline-flex items-center gap-2 text-xs text-gray-400">
          Follow-up suggestions <ComingSoonBadge phase="Phase 2" />
        </span>
        <span className="inline-flex items-center gap-2 text-xs text-gray-400">
          Token usage <ComingSoonBadge phase="Phase 2" />
        </span>
      </div>
    </section>
  )
}
