# Roadmap

---

## What This Agent Does

The Local Data Analysis Agent is a personal, browser-based analyst a single power user reaches for many times a day. The user uploads tabular data (CSV, Excel, and tables extracted from PDFs) into a persistent dataset library, then asks questions in natural language. The agent plans an analysis strategy, writes pandas code, executes it LOCALLY against the real data, inspects results and iterates until the answer holds, then replies in prose with the key numbers, interactive charts, and summary tables — always able to show the exact code it ran. Sessions are long-lived: datasets stay loaded, conversation history carries across turns so follow-ups resolve naturally, and multiple files can be joined and compared.

## Who Uses It

A single technical power user (data analyst / operator) running the app locally on their own machine. They work with the same datasets across multiple days and act on the answers, so correctness and an audit trail matter.

## Core Problem Being Solved

Replaces the slow manual loop of opening a notebook, writing pandas, re-running, and eyeballing results for every ad-hoc question — while keeping raw data on the machine. Cloud notebook/BI tools either send data to the cloud or can't do open-ended analytical reasoning; this agent does real iterative analysis locally.

## Success Criteria

- [ ] A quantitative answer's key number equals the value computed by running pandas over the FULL dataset, and the exact code is shown.
- [ ] Raw data rows never leave the machine — only schema + PII-masked sample rows reach the LLM (asserted).
- [ ] Follow-up questions resolve against conversation history without restating context.
- [ ] Every executed step (code + captured output) is persisted as an audit trail.
- [ ] Per-query token counts are shown, with a warning on unusually high spend; dollar cost is never shown.

## What This Agent Does NOT Do (Out of Scope)

- No multi-user / cloud hosting / auth — it is a single-user local app.
- No sending raw data rows to any cloud service, ever.
- No showing dollar cost (token counts only).
- No live database / warehouse connections — file uploads only.
- No scheduled/automated pipelines — interactive use only.
- No model fine-tuning or learning from feedback.

## Key Constraints

- Files up to ~100MB.
- All computation runs locally; only schema + masked samples reach Gemini.
- Bounded analysis iteration (`max_steps`, default 6) to cap latency and cost.
- Single-origin local web app served at `http://localhost:8001/app/`.

## Phases of Development

> Phase 1 is the smallest first-time-right user-testable win: upload one CSV → auto-profile → ask one question → planned, locally-executed, iterated pandas analysis → prose answer with key numbers + the collapsible code. Everything else ships as clearly-labelled non-functional stubs.

### Phase 1 — Upload, Profile, Ask, Answer (real end-to-end)

- **Goal:** The user uploads one CSV, sees an auto-generated profile (columns, types, ranges, missing values), asks one natural-language question, and receives a prose answer with the key numbers PLUS the collapsible pandas code the agent wrote and ran locally against the real data (bounded iteration). PII-masking is enforced on any sample rows sent to Gemini.
- **Independent slices (parallel build units):**
  - `backend-core` (backend) — dataset ingestion+profiling+PII masking, local subprocess code-execution sandbox, the LangGraph plan→write-code→execute→reflect→answer graph, audit-trail persistence, `/api` endpoints, structured logging. Deps: none.
  - `frontend-app` (frontend) — upload panel, profile view, question box, answer view with collapsible code + step trace; clearly-labelled NON-FUNCTIONAL stubs for: dataset library sidebar, charts, follow-up suggestions, token badge, multi-file join, export. Deps: none (codes against the API contract in `spec/api.md`).
- **Key surfaces / files:**
  - `backend-core`: `src/db/models.py` (Dataset, DatasetProfile, Query, AnalysisStep), `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/analysis/executor.py` (subprocess sandbox), `src/analysis/profiler.py`, `src/analysis/masking.py`, `src/api/datasets.py`, `src/api/queries.py`, `src/prompts/*.md`, `src/config/settings.py`, `alembic/versions/*`.
  - `frontend-app`: `frontend/src/app/page.tsx`, `frontend/src/components/*`, `frontend/tests/e2e/smoke.spec.ts`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest tests/phase1 -q && (cd frontend && pnpm build) && npx playwright test frontend/tests/e2e/ --reporter=line` (real Gemini via `AGENT_GEMINI_API_KEY` in `.env`; SQLite driver — SQLite IS the production DB here).
- **How the user tests it (handoff seed):** Run `cd frontend && pnpm build` then `uv run python -m src`, open `http://localhost:8001/app/`. Upload a real CSV (e.g. sales data). Confirm the profile panel lists every column with type/range/missing counts. Type a question like "What is the total revenue by region?" and submit; a spinner shows progress. Expect a prose answer stating the key numbers, and a collapsible "Show code" section revealing the pandas code + its output for each step. Labelled stubs (grey "Coming soon" badges, non-functional): library sidebar, charts, follow-up suggestions, token badge, join, export.

### Phase 2 — Conversation, Charts & Guidance

- **Goal:** Turn the single-shot Q&A into a real analysis session: multi-turn conversation memory (follow-ups resolve), 2–3 follow-up suggestions after each answer, clarifying questions on ambiguity, interactive charts + summary tables, and a per-query token badge with a high-spend warning. (Capabilities: Conversational Analysis Session; Visualization portion of Visualization/Library/Export; token display within Iterative Code Analysis.)
- **Independent slices (parallel build units):**
  - `backend-session` (backend) — session/history persistence, history injection into `plan`, follow-up-suggestion + clarify-vs-guess logic, token-usage capture, chart-spec + summary-table generation from local results. Deps: none.
  - `frontend-session` (frontend) — chat transcript UI, clickable suggestions, clarifying-question prompt, interactive chart component, sortable summary table, token badge + warning. Deps: consumes `backend-session` API fields (contract in `spec/api.md`); build concurrently against the contract, integrate at gate.
- **Key surfaces / files:**
  - `backend-session`: `src/db/models.py` (Session, extend Query with suggestions/token_usage/chart_spec), `src/graph/nodes.py` (history + suggest + clarify + chart), `src/graph/state.py`, `src/api/queries.py`, `src/api/sessions.py`, `src/prompts/*.md`, `alembic/versions/*`.
  - `frontend-session`: `frontend/src/components/Chart.tsx`, `SummaryTable.tsx`, `Suggestions.tsx`, `TokenBadge.tsx`, `Transcript.tsx`, `frontend/tests/e2e/session.spec.ts`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest tests/phase2 -q && (cd frontend && pnpm build) && npx playwright test frontend/tests/e2e/ --reporter=line` (real Gemini via `.env`; SQLite).
- **How the user tests it (handoff seed):** Ask "average sales by month?", then "and just for 2024?" — the second answer is scoped to 2024 without restating. Confirm 2–3 clickable follow-up suggestions appear and reference real columns. Ask something ambiguous ("show me the top ones") and confirm a clarifying question is returned. Confirm answers with a trend render an interactive chart and a sortable summary table, and each answer shows a token badge (with a warning on a deliberately large query). Still-stubbed: library sidebar, Excel/PDF upload, multi-file join, export.

### Phase 3 — Dataset Library, Multi-file & Export

- **Goal:** Make the library persistent and multi-format, enable cross-file analysis, and let the user take data out: Excel (.xlsx) and PDF-table ingestion, a persistent multi-day dataset library UI (select/rename/delete), multi-file join/compare, and export of cleaned data or results. (Capabilities: remaining Dataset Ingestion & Profiling formats; Library/Multi-file/Export portions of Visualization/Library/Export.)
- **Independent slices (parallel build units):**
  - `backend-ingest` (backend) — Excel + PDF-table ingestion + profiling, export (CSV/XLSX) endpoints. Deps: none.
  - `backend-multifile` (backend) — multi-dataset session, join-key proposal, cross-file analysis in the graph. Deps: none (disjoint files from `backend-ingest`).
  - `frontend-library` (frontend) — library sidebar (list/select/rename/delete), multi-file selector + join-key picker, export buttons. Deps: consumes the two backend slices' API fields; build against contract, integrate at gate.
- **Key surfaces / files:**
  - `backend-ingest`: `src/analysis/ingest/excel.py`, `src/analysis/ingest/pdf.py`, `src/analysis/export.py`, `src/api/datasets.py`, `src/api/export.py`.
  - `backend-multifile`: `src/graph/nodes.py` (multi-dataset context + join), `src/analysis/join.py`, `src/api/sessions.py`.
  - `frontend-library`: `frontend/src/components/LibrarySidebar.tsx`, `DatasetPicker.tsx`, `ExportMenu.tsx`, `frontend/tests/e2e/library.spec.ts`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest tests/phase3 -q && (cd frontend && pnpm build) && npx playwright test frontend/tests/e2e/ --reporter=line` (real Gemini via `.env`; SQLite).
- **How the user tests it (handoff seed):** Upload a real .xlsx and a PDF containing a table; both appear profiled in the library sidebar and persist across a reload. Select two datasets, accept the proposed join key, and ask a cross-file question — confirm the joined result is correct. Rename and delete a dataset. Export a result and confirm the downloaded file matches the on-screen table. No stubs remain — every capability is live.
