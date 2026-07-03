# Agent

---

## Agent Architecture Pattern

**Chosen:** Graph (LangGraph) — a ReAct-style plan → act → observe loop with a bounded reflection cycle. Multi-step with a conditional loop-back edge (reflect → write_code) and an error branch, which a linear chain cannot express.

Patterns composed (from `harness/patterns/agentic-ai.md`):
- **#22 LLM-Generated Code Execution** — the core: the LLM writes pandas code, the system runs it against the real data. Chosen over a hardcoded op-list so arbitrary open-ended questions work.
- **#6 Planning** — `plan` node produces an explicit strategy before coding, for multi-step analytical questions.
- **#17 Reasoning (ReAct)** — write_code → execute → reflect interleaves reasoning with action/observation.
- **#4 Reflection** — bounded self-critique loop that inspects results/errors and refines code until the answer holds.
- **#8 Memory Management** — conversation history injected into `plan` (Phase 2) so follow-ups resolve.
- **#18 Guardrails** — PII-masking boundary + subprocess sandbox; only schema + masked sample reach the LLM.
- **#12 Exception Handling** — code failures captured as steps and retried (bounded); LLM failures retried then surfaced.
- **#19 Evaluation & Monitoring** — structured logging + step audit trail from Phase 1.

Reflection/memory are wired in Phase 1's skeleton (loop present; history field exists) and fully exercised from Phase 1 (loop) / Phase 2 (history) — no separate upgrade phase is required beyond the requirements phases.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| plan | Gemini | `gemini-2.5-pro` | strategy quality over latency |
| write_code | Gemini | `gemini-2.5-pro` | correct pandas code generation |
| reflect | Gemini | `gemini-2.5-pro` | reliable done/continue + error diagnosis |
| answer | Gemini | `gemini-2.5-pro` | production-quality prose + numbers |
| suggest (Phase 2) | Gemini | `gemini-2.5-flash` (configurable) | light task, latency-sensitive |

Model IDs are env-configurable via `AGENT_LLM_MODEL`; provider fixed to Gemini via `AGENT_LLM_PROVIDER=gemini` / auto-detected from `AGENT_GEMINI_API_KEY`.

**Fallback behaviour:** each LLM node retries once with backoff; on continued failure it sets `state["error"]` and routes to `handle_error`, which finalizes the query as `failed` with a surfaced message. Not a stub path — tests hit real Gemini.

**Prompt strategy:** system/user split, system prompts in `src/prompts/*.md`. `write_code` uses a strict output contract (a single fenced Python block assigning `RESULT`); `reflect` returns structured JSON `{done: bool, reason: str}`; `answer` returns prose + a structured key-numbers block (+ chart_spec/suggestions in Phase 2). Outputs are validated (guardrail) before use.

---

## Tools & Tool Calling

The "tool" is the local code executor; the LLM produces code rather than choosing among many tools.

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `execute_local` | Run generated pandas in an isolated subprocess against the real file | code str, dataset path(s) | `{stdout, result_json, error, traceback, duration_ms}` | persists an `AnalysisStep` row; reads local file |
| `build_chart` (Phase 2) | Produce a chart spec from a local result | result records, intent | chart_spec JSON | none |
| `export_result` (Phase 3) | Write cleaned/result data to CSV/XLSX | query/dataset id, format | file path | writes a file for download |

**Tool selection strategy:** deterministic — the graph always routes generated code to `execute_local`; no LLM tool-routing.

**Tool failure handling:** a failed/timed-out execution is captured as a failed `AnalysisStep`; `reflect` sees the error and either retries with corrected code (within `max_steps`) or gives up gracefully and answers with best-available results, flagging the limitation.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                       # Query id, set at init
    session_id: str | None            # set at init (Phase 2)

    # Input
    question: str                     # from the trigger
    dataset_ids: list[str]            # active dataset(s)
    dataset_paths: list               # local file path(s) — read only in the sandbox
    schema_context: str               # profile summary (from DatasetProfile)
    masked_sample: str                # PII-masked sample rows — ONLY data seen by LLM
    history: list                     # prior turns [{question, answer}] (Phase 2)
    join_context: str                 # multi-dataset merge guidance (Phase 3)
    proposed_join_key: str | None     # detected shared join column (Phase 3)

    # Pipeline data (populated progressively)
    plan: str                         # from plan node
    pending_code: str                 # code awaiting execution
    steps: list                       # [{code, stdout, result_json, error, duration_ms}]
    current_step: int                 # loop counter
    max_steps: int                    # bound, default 6
    reflect_done: bool                # reflect decision: answer when True

    # Output
    answer: str                       # prose + key numbers
    shown_code: list                  # steps surfaced to UI
    assumptions: list                 # flagged assumptions
    clarifying_question: str | None   # set when agent asks instead of answering (Phase 2)
    chart_spec: dict | None           # Phase 2
    suggestions: list                 # Phase 2
    token_usage: dict                 # {prompt, completion, total} accumulated

    # Control
    error: str | None                 # set by any node on fatal failure
    status: str | None                # completed | failed
```

---

## Nodes / Steps

### `node_plan`
**Reads:** question, schema_context, masked_sample, history. **Writes:** plan, token_usage.
**LLM:** yes — `gemini-2.5-pro`, returns a short numbered strategy; (Phase 2) may instead set `clarifying_question` when ambiguous.
**Behaviour:** produces the analysis strategy from schema + masked sample (+ history); decides clarify-vs-guess.

### `node_write_code`
**Reads:** plan, steps, schema_context. **Writes:** appends pending code to state, token_usage.
**LLM:** yes — emits one pandas block assigning `RESULT`, informed by prior step outputs/errors.

### `node_execute_local`
**Reads:** pending code, dataset_ids. **Writes:** steps (append captured result), current_step; persists `AnalysisStep`.
**LLM:** no.
| System | Operation | On Failure |
|--------|-----------|------------|
| Local subprocess | run pandas on real file | partial — capture error as a failed step, continue to reflect |
**Behaviour:** the privacy-safe execution boundary — runs on raw local data, captures everything, persists the audit row.

### `node_reflect`
**Reads:** steps, plan, question. **Writes:** decision (done/continue), token_usage.
**LLM:** yes — structured `{done, reason}`. Loops to write_code if not done AND `current_step < max_steps`, else to answer.

### `node_answer`
**Reads:** steps, question, plan. **Writes:** answer, shown_code, assumptions, (Phase 2) chart_spec; token_usage.
**LLM:** yes — composes prose + key numbers; assembles the shown code; flags assumptions; produces `chart_spec` (NOT suggestions).

### `node_suggest`
**Reads:** question, answer, schema_context. **Writes:** suggestions; token_usage.
**LLM:** yes — `gemini-2.5-flash` (light, latency-sensitive) — produces 2–3 follow-up question suggestions. Runs between `answer` and `finalize`.

### `node_finalize` / `node_handle_error`
Persist final `Query` status/outputs; handle_error sets status=failed with the surfaced message.

---

## Graph / Flow Topology

```
START
  │
  ▼
node_plan ──(error)──────────────► node_handle_error ──► END
  │  │
  │  └──(clarifying_question set)─► node_finalize ──► END
  ▼
node_write_code ──(error)────────► node_handle_error
  │
  ▼
node_execute_local ──(error)─────► node_handle_error
  │
  ▼
node_reflect
  │   │
  │   └──(not done AND current_step<max_steps)──► node_write_code
  ▼ (done OR step limit)
node_answer ──(error)────────────► node_handle_error
  │
  ▼
node_suggest
  │
  ▼
node_finalize ──► END
```

**Conditional edges:**

| Source | Condition | Target |
|--------|-----------|--------|
| node_plan | `state["error"]` | node_handle_error |
| node_plan | `state.get("clarifying_question")` | node_finalize |
| node_plan | else | node_write_code |
| node_execute_local | `state["error"]` (infra, not code error) | node_handle_error |
| node_reflect | not done AND `current_step < max_steps` | node_write_code |
| node_reflect | done OR limit reached | node_answer |
| node_answer | `state["error"]` | node_handle_error |
| node_answer | else | node_suggest |

(`node_suggest → node_finalize` and `node_finalize → END` are unconditional edges.)

(A pandas code error is NOT a fatal `state["error"]` — it is a captured step that reflect handles. Only infra failures set `error`.)

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| Within a run | LangGraph state | plan, steps, counters |
| Across runs | SQLite (Query, AnalysisStep) | audit trail, past answers |
| Conversation | `history` in state from `Query` rows for the session (Phase 2) | prior {question, answer} turns |

**Context window management:** only schema + masked sample (not full data) ever enter the prompt; history truncated to the most recent N turns (older summarized) in Phase 2.

---

## Human-in-the-Loop Checkpoints

| Checkpoint | Shown | Expected action | Default |
|------------|-------|-----------------|---------|
| Clarifying question (Phase 2) | one clarifying question when ambiguous | user replies with a new turn | if user reasks without clarifying, agent gives a best guess flagged with assumptions |

Not a blocking graph pause — the graph finalizes with the clarifying question; the user's reply is the next run.

---

## Error Handling & Recovery

**Node-level:** each node try/excepts; infra failures set `state["error"]` and route to handle_error. Code-execution errors are captured as failed steps (not fatal).

**Graph-level (handle_error):** reads `state.error`, `run_id`; updates `Query.status="failed"`, `error_message`, timestamp; logs with run_id; terminates.

**Resume/retry:** LLM node retries once with backoff. Code errors retried by the reflect→write_code loop within `max_steps`. On step-limit exhaustion the agent answers with best-available results and flags the limit.

**Partial failure:** a failed step degrades gracefully — the agent still answers, flagging uncertainty; it never crashes the server.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| Trace | one logical run per query, one log span per node | structured stdout logs (LangSmith optional via `LANGCHAIN_TRACING_V2` if key set) |
| LLM calls | model, prompt/completion tokens, latency | structured log + `Query.token_usage` |
| Tool calls | executed code (hash), success/error, duration | structured log + `AnalysisStep` |
| Run outcome | status, total duration, error | SQLite + log |

Observability is wired in Phase 1 (structured request/response logging on every node + the step audit trail); LangSmith tracing enabled when `LANGCHAIN_API_KEY` is present.

---

## Concurrency Model

- **Run isolation:** one query at a time per session; the API scopes everything by `run_id`/`session_id`. Concurrent queries across sessions are isolated by id.
- **Parallel nodes within a run:** none — the analysis loop is inherently sequential.
- **Checkpointing:** none required in Phase 1 (runs are short); `SqliteSaver` may be added if long clarifying pauses need resumption.

---

## Graph Assembly (`src/graph/agent.py`)

```python
graph = StateGraph(AgentState)

graph.add_node("plan", node_plan)
graph.add_node("write_code", node_write_code)
graph.add_node("execute_local", node_execute_local)
graph.add_node("reflect", node_reflect)
graph.add_node("answer", node_answer)
graph.add_node("suggest", node_suggest)
graph.add_node("finalize", node_finalize)
graph.add_node("handle_error", node_handle_error)

graph.set_entry_point("plan")

graph.add_conditional_edges("plan", route_after_plan, {
    "handle_error": "handle_error",
    "finalize": "finalize",          # clarifying question
    "write_code": "write_code",
})
graph.add_conditional_edges("write_code", err_or, {
    "handle_error": "handle_error", "execute_local": "execute_local"})
graph.add_conditional_edges("execute_local", err_or, {
    "handle_error": "handle_error", "reflect": "reflect"})
graph.add_conditional_edges("reflect", route_after_reflect, {
    "write_code": "write_code", "answer": "answer"})
graph.add_conditional_edges("answer", err_or, {
    "handle_error": "handle_error", "suggest": "suggest"})
graph.add_edge("suggest", "finalize")
graph.add_edge("finalize", END)
graph.add_edge("handle_error", END)

agentic_ai = graph.compile()
```
