# UI

---

## UI Type

Single-page web app (Next.js 15 + React 19 static export, Tailwind v4), served at `http://localhost:8001/app/`. A workbench layout: library sidebar (left), main analysis panel (center), profile/details (contextual).

## Views / Screens

### Screen: Analysis Workbench (single page)

**Purpose:** Upload data, see its profile, ask questions, read answers with code, explore charts, manage the library, export.

**Key elements:**
- **Upload panel** — drag/drop or file picker (Phase 1: CSV; Phase 3: xlsx/pdf). Shows a working spinner during ingest.
- **Profile view** — table of columns with type, range, missing counts, PII flag (Phase 1, real).
- **Question box** — natural-language input + submit; working spinner while the agent runs (Phase 1, real).
- **Answer view** — prose answer with key numbers; a collapsible "Show code" panel listing each `AnalysisStep` (code + captured output); assumptions banner when flagged (Phase 1, real).
- **Chat transcript** — prior turns in the session; follow-up input (Phase 2).
- **Follow-up suggestions** — 2–3 clickable chips under each answer (Phase 2). *Phase 1: labelled "Coming soon" stub.*
- **Chart + summary table** — interactive chart and sortable table for an answer (Phase 2). *Phase 1: labelled stub.*
- **Token badge** — per-query token counts with a high-spend warning color (Phase 2). *Phase 1: labelled stub.*
- **Library sidebar** — list/select/rename/delete datasets, multi-select + join-key picker (Phase 3). *Phase 1–2: labelled stub.*
- **Export menu** — download cleaned data/result as CSV/XLSX (Phase 3). *Phase 1–2: labelled stub.*

**Actions available:**
- Upload a file; view its profile.
- Ask a question; read the answer; expand the code/step trace.
- (Phase 2) ask follow-ups, click suggestions, answer a clarifying question, view charts/tables, see token counts.
- (Phase 3) manage the library, join datasets, export.

## Error States

- Upload errors (unparseable, too large) show an inline message; no half-created dataset.
- Agent failure shows the surfaced error, not a crash; a clarifying question renders as a prompt to reply.
- A failed analysis step is shown in the trace with its error, while the agent's best-available answer still renders.
- Every long operation shows a working spinner (never a frozen UI). Stubs carry a clearly-labelled "Coming soon" badge so they are never mistaken for bugs.

## Tech Stack

Next.js 15 + React 19, Tailwind v4, static export (`output: 'export'`, `basePath: '/app'`), Recharts for charts (Phase 2). Playwright E2E in `frontend/tests/e2e/`.
