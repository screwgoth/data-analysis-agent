"""Result-feedback masking (Phase-1 QA carryover, actioned in Phase 2).

Raw cell values from an executed step's result must NOT re-enter any LLM prompt in
the write_code / reflect feedback loop — they are masked/aggregated first. The FULL
unmasked result is still persisted on the AnalysisStep audit row (local only).
"""
import pandas as pd
import pytest
from sqlalchemy.orm import Session

import db.session as session_module
import graph.nodes as nodes
from db.models import AnalysisStep


_RAW_STEP = {
    "step_index": 0,
    "code": "RESULT = df.head().to_dict('records')",
    "stdout": "",
    "result_json": [
        {"name": "Alice Smith", "email": "alice@corp.com", "revenue": 1000},
        {"name": "Bob Jones", "email": "bob@corp.com", "revenue": 2000},
    ],
    "error": None,
    "duration_ms": 3,
}

_RAW_MARKERS = ["alice@corp.com", "bob@corp.com", "Alice Smith", "Bob Jones"]


def _capture_prompt(monkeypatch):
    captured = {}

    def fake_call(prompt, *, system, model=None):
        captured["prompt"] = prompt
        # Minimal valid downstream output so the node completes.
        return ("```python\nRESULT = 1\n```", {"prompt": 1, "completion": 1, "total": 2})

    monkeypatch.setattr(nodes, "_call_llm", fake_call)
    return captured


def test_write_code_prompt_never_carries_raw_result_cells(monkeypatch):
    captured = _capture_prompt(monkeypatch)
    state = {
        "run_id": "r1",
        "question": "next step?",
        "plan": "p",
        "schema_context": "cols",
        "steps": [_RAW_STEP],
    }
    nodes.node_write_code(state)
    prompt = captured["prompt"]
    for marker in _RAW_MARKERS:
        assert marker not in prompt, f"raw cell value {marker!r} leaked into write_code prompt"


def test_reflect_prompt_never_carries_raw_result_cells(monkeypatch):
    captured = _capture_prompt(monkeypatch)
    state = {
        "run_id": "r1",
        "question": "done?",
        "plan": "p",
        "steps": [_RAW_STEP],
    }
    nodes.node_reflect(state)
    prompt = captured["prompt"]
    for marker in _RAW_MARKERS:
        assert marker not in prompt, f"raw cell value {marker!r} leaked into reflect prompt"


def test_execute_local_persists_full_unmasked_result(tmp_path, _isolated_db, monkeypatch):
    # Real subprocess execution; the audit row must keep the FULL raw result.
    df = pd.DataFrame(
        {"name": ["Alice Smith", "Bob Jones"], "email": ["alice@corp.com", "bob@corp.com"]}
    )
    csv_path = tmp_path / "people.csv"
    df.to_csv(csv_path, index=False)

    state = {
        "run_id": "run-audit-1",
        "pending_code": "RESULT = df.to_dict('records')",
        "dataset_paths": [str(csv_path)],
        "current_step": 0,
        "steps": [],
    }
    out = nodes.node_execute_local(state)
    step = out["steps"][-1]
    assert step["error"] is None, step["error"]

    with Session(session_module._engine) as s:
        rows = (
            s.query(AnalysisStep)
            .filter(AnalysisStep.query_id == "run-audit-1")
            .all()
        )
    assert len(rows) == 1
    persisted = rows[0].result_json
    blob = str(persisted)
    # Full unmasked values survive in the LOCAL audit trail.
    assert "alice@corp.com" in blob
    assert "Alice Smith" in blob
