from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                       # Query id, set at init
    session_id: str | None            # set at init (Phase 2)

    # Input
    question: str
    dataset_ids: list                 # active dataset id(s)
    dataset_paths: list               # local file path(s) — read only in the sandbox
    schema_context: str               # profile summary (from DatasetProfile)
    masked_sample: str                # PII-masked sample rows — ONLY data seen by LLM
    history: list                     # prior turns (Phase 2)
    join_context: str                 # multi-dataset merge guidance (Phase 3)
    proposed_join_key: str | None     # detected shared join column (Phase 3)

    # Pipeline data
    plan: str
    pending_code: str                 # code awaiting execution
    steps: list                       # [{step_index, code, stdout, result_json, error, duration_ms}]
    current_step: int
    max_steps: int
    reflect_done: bool

    # Output
    answer: str
    shown_code: list
    assumptions: list
    clarifying_question: str | None
    chart_spec: dict | None
    suggestions: list
    token_usage: dict                 # {prompt, completion, total, warn}

    # Control
    error: str | None
    status: str | None                # completed | failed
