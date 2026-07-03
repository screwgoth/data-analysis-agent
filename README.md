# Local Data Analysis Agent

> **All commands run from the repo root** (where `pyproject.toml` and `alembic.ini` live). There is no subdirectory to `cd` into (except the one-time `cd frontend` for the UI build). Every Python command is prefixed with `uv run` — bare `python`/`alembic`/`pytest` will fail unless the venv is manually activated.

A single-user, fully-local browser app: upload a CSV, get an auto-generated profile, ask a question in natural language, and receive a prose answer with the key numbers plus the exact pandas code the agent wrote and ran **locally** against your real data. Raw data never leaves the machine — only the schema and a PII-masked sample reach the LLM (Google Gemini).

## Phase 1 — Upload, Profile, Ask, Answer

Phase 1 delivers the real end-to-end path: CSV upload → profile → one question → bounded plan→write-code→execute→reflect→answer loop → prose answer with the collapsible code/step trace. The dataset-library sidebar, charts, follow-up suggestions, token badge, multi-file join, and export are clearly-labelled non-functional stubs until later phases.

### Prerequisites — environment

Set these in `.env` (gitignored; presence only, never commit keys):

```
AGENT_GEMINI_API_KEY=<your Gemini key>
AGENT_LLM_PROVIDER=gemini
AGENT_LLM_MODEL=gemini-2.5-pro
AGENT_DATABASE_URL=sqlite:///./data/agent.db   # optional; this is the default
```

Optional: `LANGCHAIN_API_KEY` enables LangSmith tracing.

### Set up + migrate the database

```bash
uv sync --extra dev
uv run alembic upgrade head
uv run alembic current      # must print a revision hash (e.g. d846a1ecafa8 (head)), not blank
```

### Run the app

```bash
cd frontend && pnpm build && cd ..   # builds the Next.js static export into frontend/out
uv run python -m src                 # starts the server on port 8001
```

Then open **http://localhost:8001/app/**. Upload a CSV, confirm the profile panel, ask e.g. "What is the total revenue by region?", and expand "Show code" to see the pandas the agent ran.

API endpoints (Phase 1): `POST /api/datasets` (CSV upload + profile), `POST /api/queries` (run the analysis graph), `GET /health`.

### Phase 1 gate command

```bash
uv run alembic upgrade head && uv run pytest tests/phase1 -q
```

Tests hit the real Gemini API using the key in `.env` (they skip only if no key is present) and use an isolated temporary SQLite DB. SQLite is the production database for this deliberately local, single-user app.

> Excel (`.xlsx`) and PDF-table ingestion are **not yet** supported — Phase 1 is CSV only (Phase 3).

---

## Phase 2 — Conversation, Charts & Guidance

Phase 2 turns the single-shot Q&A into a real analysis **session**:

- **Conversation memory / sessions** — a `POST /api/sessions` opens a conversation over one or more datasets; every `POST /api/queries` belongs to a session (one is auto-created if you omit `session_id`). Prior `{question, answer}` turns are loaded into the agent's `plan` node so follow-ups like "and just for 2024?" resolve **without restating context**. History is truncated to the most recent `AGENT_HISTORY_MAX_TURNS` turns (default 8).
- **Clarifying questions** — when a question is genuinely ambiguous, the agent returns a `clarifying_question` instead of guessing (no analysis steps run); if you re-ask without clarifying, it makes a best guess flagged in `assumptions`.
- **Follow-up suggestions** — after each answer a light `node_suggest` (`gemini-2.5-flash`) returns 2–3 concrete follow-up questions that reference real columns (`suggestions`).
- **Charts + summary tables** — `node_answer` derives a `chart_spec` (bar type + series + a `table` structure) from the **local result** (never raw data, never via the LLM) when the answer has a chartable breakdown; `null` otherwise.
- **Token badge + high-spend warning** — real prompt/completion/total tokens are accumulated across all nodes into `token_usage`; `token_usage.warn` is `true` when the total exceeds `AGENT_TOKEN_WARN_THRESHOLD` (default 20000). Dollar cost is never shown.
- **Result-feedback masking** — a step's `result_json` is masked/aggregated (via `src/analysis/masking.py:mask_result_feedback`) before it re-enters any LLM prompt in the write-code/reflect/answer loop; the FULL unmasked result is still persisted on the `AnalysisStep` audit row (local only).

New endpoints: `POST /api/sessions` (create a session over `dataset_ids`), `GET /api/sessions/{id}` (ordered Query history). `POST /api/queries` now accepts an optional `session_id` and returns `chart_spec`, `suggestions`, `clarifying_question`, and `token_usage.warn`.

Optional Phase-2 env (all have sensible defaults):

```
AGENT_HISTORY_MAX_TURNS=8          # recent turns kept verbatim in plan context
AGENT_TOKEN_WARN_THRESHOLD=20000   # total tokens above → warn badge
AGENT_SUGGEST_MODEL=gemini-2.5-flash
```

### Phase 2 gate command

```bash
uv run alembic upgrade head && uv run pytest tests/phase2 -q
```

Still-stubbed until Phase 3: dataset-library sidebar, Excel/PDF upload, multi-file join, export.

---

## Phase 3 — Dataset Library, Multi-file & Export

Phase 3 makes the library persistent and multi-format, and lets you take data out.

- **Excel + PDF ingestion** — `POST /api/datasets` now accepts `.csv`, `.xlsx`, and `.pdf` in addition to CSV, dispatched by file extension. Excel is read with pandas/openpyxl (the **first sheet** of a multi-sheet workbook). PDF tables are extracted best-effort with `pdfplumber` — the **largest table** found is used, its first row as the header. Every upload is normalized to a canonical local `data.csv` under `data/datasets/<id>/` so the subprocess executor keeps reading local CSV only. An unparseable file — including a PDF with no extractable table — returns **400** (never a 500 crash); files over ~100MB return **413**.
- **Persistent library CRUD** — `GET /api/datasets` (list all: id, name, source_format, row/col counts, created_at), `GET /api/datasets/{id}` (dataset + its profile), `PATCH /api/datasets/{id}` (rename), `DELETE /api/datasets/{id}` (removes the DB row, its profile, **and** the local file(s) from disk, Windows-safe).
- **Export** — `GET /api/queries/{id}/export?format=csv|xlsx` streams the query's final result as a downloadable file with the correct `Content-Disposition` and media type. Built locally from the persisted `AnalysisStep.result_json`. Unknown query → **404**; build failure → **500**.
- **Multi-file join / cross-file analysis** — a session and `POST /api/queries` can span multiple `dataset_ids`. When 2+ datasets are selected, the runner loads each as its own DataFrame in the sandbox (`df1`, `df2`, … — labelled with its filename in the prompt) and `src/analysis/join.py::propose_join_key` deterministically proposes a shared join column (a column name present in every dataset with a compatible dtype family, id/key-like columns preferred). The proposed key is injected into the plan/write-code prompts so a cross-file question ("total amount by region, joining orders to customers on customer_id") produces a real local `pd.merge(...)` + aggregation. If no confident shared key is found, the agent states its assumption or asks one clarifying question. Privacy holds across every dataset: only schema + PII-masked samples reach Gemini — raw rows for all files stay local. Single-dataset behavior is unchanged.

New Python deps: `openpyxl` (Excel) and `pdfplumber` (PDF tables).

> PDF table extraction is inherently best-effort — a PDF is a layout format, not a data format. Ruled or well-aligned tables extract reliably; free-form layouts may not, and degrade gracefully to a 400 rather than crashing.

### Phase 3 gate command

```bash
uv run alembic upgrade head && uv run pytest tests/phase3 -q
```

---

## About the harness (below) — Zero Shot SDD Harness for Building Agents

Give it a one-line idea. Walk away with a working, tested, phased agent.

A lean, Claude-Code-native harness for building agentic software **spec-first**. One person with an idea and one API key can drive a real, production-shaped agent into existence — and a senior engineer opening the result finds a conventional, reviewable stack, not generated mush.

---

## The Spirit

Six convictions the whole repo is built around:

1. **Spec is the source of truth.** The spec is written before the code, always. When spec and code disagree, the spec wins and the code is fixed (`/zero-shot-sync`). Every AI session reads the same requirements instead of re-deriving them.
2. **Built for two audiences at once.** A non-coder drives it with a single sentence; a senior engineer inherits a clean FastAPI + LangGraph stack they can read, review, and own. Neither audience is an afterthought.
3. **Lean harness, not a framework.** `harness/` is engineering *mindfulness* — rules and patterns that keep every session consistent — deliberately Claude-Code-only and kept small. The product runtime stays provider-agnostic; the harness does not.
4. **Smallest first-time-right win, phase by phase.** Each phase ships the smallest increment a human can actually test, and it must work the *first* time they test it — real on the tested path, with clearly-labelled stubs for everything still to come. No rough edges on the path you're handed.
5. **A human gates every phase.** The build is autonomous *within* a phase and stops at each boundary for you to test the increment. You stay in control of what "done" means.
6. **Real LLM/API or it doesn't count.** Gates, tests, and evals run against the real model with keys from `.env`. A stubbed pass is not a pass.

---

## What This Is

A starting point for building AI agents spec-first. The repo ships with:

- A working **baseline agent** in `src/` (FastAPI + LangGraph + SQLite, provider-agnostic LLM — Anthropic or Gemini, `transform_text` as the capability slot) — tests pass out of the box
- A **spec template** in `spec/` covering roadmap, architecture, capabilities, data model, API, UI, and agent graph
- Three **zero-shot skills** (`/zero-shot-build`, `/zero-shot-fix`, `/zero-shot-sync`)
- A four-agent **team** — agent-builder orchestrates (plans, fans out, owns git/PR); spec-writer is the single design authority; code-generator implements one slice per instance (parallelised); qa-auditor reviews and gates
- Engineering rules and patterns in `harness/` so every Claude Code session is consistent
- **Human testing gate between phases** — autonomous within a phase, you test each increment before the next starts

---

## How to Use This

### Step 1 — Clone

```bash
git clone https://github.com/smallTechOrg/zero-shot-sdd-harness.git my-agent
cd my-agent
```

### Step 2 — Open in Claude Code

```bash
claude
```

### Step 3 — Build

```
/zero-shot-build An agent that monitors my Shopify store for low-inventory products and drafts restock emails to suppliers
```

One intake round (scope, stack, API keys → fill `.env`), then the agent builds phase by phase and stops at each boundary for you to test.

---

## What Happens (Intake → Phase by Phase)

```
Your idea
    ↓
INTAKE — scope, stack, LLM provider, constraints; fill .env with the required API key
    ↓
[spec-writer]  → Full spec: architecture + agent-graph + phased plan (self-reviewed)
    ↓
[agent-builder] → Feature branch + PR, scaffold
    ↓
per phase — all slices concurrently:
    [code-generator: slice-a]  ──→  [qa-auditor: slice-a]  ─┐
    [code-generator: slice-b]  ──→  [qa-auditor: slice-b]  ─┤→  commit + push
    [code-generator: slice-c]  ──→  [qa-auditor: slice-c]  ─┘
    ↓
HUMAN TESTING GATE — exact run commands + expected result; you confirm before next phase
    ↓
(issue → qa-auditor classifies SPEC-vs-CODE → code-generator fixes → re-gate)
    ↓
repeat per phase → SHIP
```

Phase 1 is the smallest first-time-right win — real on the tested path, with labelled stubs for everything coming later. Each later phase wires one more stub into real functionality.

---

## Repo Layout

```
src/                ← baseline agent (FastAPI + LangGraph + SQLite, Anthropic/Gemini)
  api/              ← FastAPI routers (create_app, health, runs)
  config/           ← Pydantic BaseSettings
  db/               ← SQLAlchemy models + session
  domain/           ← Pydantic request/response models
  graph/            ← LangGraph nodes, edges, state, runner  ← CAPABILITY SLOT
  llm/              ← LLM client + providers/ (anthropic, gemini)
  prompts/          ← prompt templates (.md)
  observability/
frontend/           ← Next.js static export (served by FastAPI at /app)
tests/
  unit/             ← passes with no API key
  integration/      ← requires real key in .env
spec/               ← your spec: roadmap, architecture, capabilities/, data, api, ui, agent
harness/
  rules/            ← ai-agents, git, secret-hygiene
  patterns/         ← spec-driven, phases, project-layout, tech-stack, code, test-driven, ui-ux, agentic-ai, engineering-practices
.claude/
  skills/           ← /zero-shot-build, /zero-shot-fix, /zero-shot-sync
  agents/           ← agent-builder, spec-writer, code-generator, qa-auditor
CLAUDE.md
pyproject.toml
alembic.ini        ← Alembic migrations (alembic/)
agent.py            ← verify setup (default); --run to start the server
.env.example
```

**Capability slot** — the three files to replace for your agent:
- `src/graph/nodes.py` — replace `transform_text` with your logic
- `src/prompts/transform.md` — replace with your system prompt
- `frontend/src/app/page.tsx` — replace the transform form with your UI

Everything else (graph wiring, API, DB, settings, tests) is already working.

---

## Running the Baseline

```bash
cp .env.example .env
# edit .env: set exactly ONE provider key —
#   AGENT_ANTHROPIC_API_KEY=<your key>   or   AGENT_GEMINI_API_KEY=<your key>
# the provider is auto-detected from whichever key is set
uv sync
python agent.py                        # verify tools, .env, deps, tests (default)
python agent.py --run                  # migrations + frontend build + start server
```

Once running:

| URL | What |
|-----|------|
| `http://localhost:8001/app/` | **UI** — transform form (the capability slot) |
| `http://localhost:8001/health` | API health check |
| `http://localhost:8001/docs` | Interactive API docs (Swagger) |

Tests:

```bash
uv run pytest tests/unit/ -v          # no key needed
uv run pytest tests/ -v               # requires real key in .env
```

---

## Rules AI Agents Follow

Full rules in `harness/rules/ai-agents.md`. Summary:

- Read the full spec before writing any code
- Never skip a phase; commit every logical unit
- Tests run against the real LLM/API using keys from `.env` — stubbed runs do not count as passing
- Each phase is tested by the human before the next phase starts
- The build record is git history + the PR + the per-phase test-handoffs

---

## FAQ

**What if I already have a stack in mind?**
State it in the idea: `/zero-shot-build [idea] — use Python + FastAPI + PostgreSQL`. Stack choices are binding.

**What if something breaks?**
Run `/zero-shot-fix [what's broken]` — qa-auditor classifies the problem (SPEC vs CODE), the right generator fixes it, qa-auditor re-gates.

**What if spec and code drift?**
Run `/zero-shot-sync` — qa-auditor classifies each divergence, generators fix, spec wins.
