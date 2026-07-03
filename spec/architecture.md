# Architecture

---

## System Overview

A single-user, fully-local web application. A Next.js static export (served by FastAPI at `/app`) is the UI; FastAPI exposes a small JSON API; a LangGraph agent plans and runs analysis; generated pandas code executes in an isolated local Python subprocess against the real uploaded files; SQLite persists datasets metadata, sessions, queries, and the per-step audit trail. Gemini (cloud) is the only external dependency and receives ONLY dataset schema + PII-masked sample rows — never raw data. All computation is local.

## Component Map

```
Browser (Next.js static export @ :8001/app/)
    │  JSON over HTTP (same origin)
    ▼
FastAPI (src/api/*)
    │
    ▼
Graph Runner (src/graph/runner.py) ──► SQLite (datasets, sessions, queries, analysis_steps)
    │
    ▼
LangGraph agent (plan → write_code → execute_local → reflect → answer)
    │                         │
    │ schema+masked sample    ▼
    ▼                    Local Python subprocess sandbox (src/analysis/executor.py)
Gemini (cloud LLM)            │  runs generated pandas on the REAL file
                             ▼
                        Local filesystem (data/datasets/<id>/)
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| UI (Next.js) | Upload, profile view, chat transcript, answer + collapsible code/step trace, charts/tables, library, export |
| API (FastAPI) | Dataset CRUD + upload, query submission, session history, export; validation; error envelopes |
| Agent (LangGraph) | Plan strategy, write code, execute locally, reflect/iterate (bounded), compose answer |
| Analysis (local) | Profiling, PII masking, subprocess code execution + capture, join, export |
| Storage (SQLite + FS) | Metadata, sessions, queries, audit trail; raw files on local disk |
| LLM (Gemini) | Planning, code generation, reflection, answer/suggestion generation — schema + masked sample only |

## Data Flow

1. Trigger: user uploads a file → `POST /api/datasets` stores it locally, profiles it, computes a PII-masked sample.
2. User submits a question → `POST /api/queries` creates a `Query` and invokes the graph runner.
3. `plan` node (Gemini) produces a strategy from schema + masked sample (+ history in Phase 2).
4. `write_code` (Gemini) emits pandas code; `execute_local` runs it in a subprocess against the REAL file, capturing stdout/result/error and persisting an `AnalysisStep`.
5. `reflect` (Gemini) inspects the step; loops back to `write_code` if more work is needed (bounded by `max_steps`), else proceeds.
6. `answer` (Gemini) composes prose + key numbers, assembles the shown code, (Phase 2) chart spec + suggestions + token usage.
7. Output: JSON with answer, shown steps, chart spec, suggestions, token usage; UI renders it.

## Local Code Execution & Audit Trail (key design)

- **Sandbox:** `src/analysis/executor.py` spawns a fresh Python subprocess per step (`subprocess.run`, Windows-compatible — no `os.exec*`). A generated runner harness loads the dataset file(s) into `df` (or `df1`, `df2` for joins) via pandas, executes the LLM-generated code, and prints a JSON envelope of `{stdout, result_repr, result_records, error, traceback}` on the last expression / an explicit `RESULT` variable.
- **Isolation & limits:** wall-clock timeout (configurable, default 30s), captured stdout/stderr, no network (documented convention + no network libs injected), memory guarded by the OS. A crash/timeout is captured as a failed step, not a server crash (`OSError`/`TimeoutExpired` caught, per existing Windows-safety practice).
- **Audit trail:** before the next step runs, `execute_local` persists an `AnalysisStep` row with `step_index`, exact `code`, `stdout`, `result_json`, `error`, `duration_ms`. The full trace is queryable and shown collapsibly in the UI. This is what makes answers reproducible/production-grade.
- **Privacy boundary:** `src/analysis/masking.py` produces the only sample that may reach Gemini. The executor runs on raw local data; the LLM nodes are passed `schema_context` + `masked_sample` strings only. A guardrail test asserts no raw PII value appears in an LLM request payload.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Gemini API | plan/code/reflect/answer generation | retry once with backoff; then set `state["error"]`, finalize with a surfaced message |
| Local Python subprocess | run generated pandas | captured as a failed step; agent reflects/retries (bounded) |
| Local filesystem | store uploaded files | upload fails with 4xx/5xx; no dataset row committed |

## Stack

- **Language:** Python 3.12 (backend), TypeScript (frontend)
- **Agent framework:** LangGraph
- **LLM provider + model:** Google Gemini — default `gemini-2.5-pro` (planning/code/reflection/answer). `gemini-2.5-flash` is the env-configurable fast alternative for light nodes (suggestions). Configured via `.env`: `AGENT_LLM_PROVIDER=gemini`, `AGENT_LLM_MODEL=gemini-2.5-pro`. Key: `AGENT_GEMINI_API_KEY` (`AQ.`-prefix). `AGENT_ANTHROPIC_API_KEY` is unused. (Other verified-working models on this key: `gemini-2.5-flash`, `gemini-3-pro-preview`, `gemini-3.5-flash`.)
- **Backend:** FastAPI (single-origin; serves the static frontend at `/app`)
- **Database + ORM:** SQLite + SQLAlchemy 2.0 (SQLite is the production DB for this local single-user app), Alembic migrations
- **Frontend:** Next.js 15 + React 19, static export (`output: 'export'`, `basePath: '/app'`), Tailwind v4
- **Dependency management:** uv + pyproject.toml (Python), pnpm (frontend)

> **Assumed:** default model `gemini-2.5-pro` (verified-working on this API key); set via `.env` `AGENT_LLM_MODEL=gemini-2.5-pro` / `AGENT_LLM_PROVIDER=gemini`.
> **Assumed:** charts rendered client-side from an agent-produced JSON chart spec (chart type + local result data); charting lib chosen by the frontend generator (e.g. Recharts) — no raw data leaves the machine to render.
> **Assumed:** PDF table extraction via a pure-Python extractor (e.g. `pdfplumber`); Excel via `openpyxl`. Final lib pinned by the ingest generator in Phase 3.

| Key library | Version | Purpose |
|-------------|---------|---------|
| langgraph | current | agent graph |
| google-genai | current | Gemini client (already in boilerplate) |
| fastapi + uvicorn | current | API + server |
| sqlalchemy + alembic | 2.0 | ORM + migrations |
| pandas | current | local analysis + profiling |
| openpyxl | current | Excel ingest (Phase 3) |
| pdfplumber | current | PDF table ingest (Phase 3) |
| recharts | current | interactive charts (Phase 2, frontend) |
| @playwright/test | current | E2E smoke |

**Avoid:** sending any raw data rows to the LLM; `os.exec*` (Windows-incompatible — use `subprocess.run`); `eval`/`exec` in-process for LLM code (must be a separate subprocess); PostgreSQL (this is a deliberately local single-user app, SQLite is the chosen prod DB).

## Deployment Model

Runs locally: `cd frontend && pnpm build` then `uv run python -m src`; one server on port 8001; UI at `http://localhost:8001/app/`. No cloud deployment.
