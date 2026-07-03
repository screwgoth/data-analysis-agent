"""LangGraph nodes for the data-analysis agent.

plan -> write_code -> execute_local -> reflect -(loop)-> ... -> answer -> finalize
LLM nodes call Gemini via the LLMClient abstraction (never the SDK directly).
Code-execution errors are captured as steps (reflect handles them); only infra
failures set state["error"] and route to handle_error.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from analysis.executor import execute_code
from config.settings import get_settings
from db.models import AnalysisStep
from db.session import create_db_session
from graph.state import AgentState
from llm.client import LLMClient
from observability.events import get_logger

_PROMPTS = Path(__file__).parent.parent / "prompts"
_log = get_logger("graph")

_CODE_FENCE_RE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL)


def _prompt(name: str) -> str:
    return (_PROMPTS / f"{name}.md").read_text(encoding="utf-8").strip()


def _call_llm(prompt: str, *, system: str) -> tuple[str, dict]:
    """Call the LLM with one retry+backoff. Raises on continued failure."""
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            return LLMClient().call_model_with_usage(prompt, system=system)
        except Exception as exc:  # noqa: BLE001 — surfaced to caller
            last_exc = exc
            if attempt == 0:
                time.sleep(1.0)
    raise RuntimeError(f"LLM call failed after retry: {last_exc}")


def _accumulate(state: AgentState, usage: dict) -> dict:
    total = dict(state.get("token_usage") or {"prompt": 0, "completion": 0, "total": 0})
    for k in ("prompt", "completion", "total"):
        total[k] = int(total.get(k, 0)) + int(usage.get(k, 0) or 0)
    total.setdefault("warn", False)  # warn logic is Phase 2
    return total


def _extract_code(text: str) -> str:
    match = _CODE_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _span(node: str, state: AgentState, **extra) -> None:
    _log.info(
        "node",
        node=node,
        run_id=state.get("run_id"),
        step=state.get("current_step"),
        tokens=(state.get("token_usage") or {}).get("total"),
        **extra,
    )


def node_plan(state: AgentState) -> AgentState:
    start = time.perf_counter()
    try:
        user = (
            f"QUESTION:\n{state['question']}\n\n"
            f"SCHEMA:\n{state.get('schema_context', '')}\n\n"
            f"PII-MASKED SAMPLE (do not trust exact masked values):\n"
            f"{state.get('masked_sample', '')}"
        )
        text, usage = _call_llm(user, system=_prompt("plan"))
        state = {**state, "plan": text, "token_usage": _accumulate(state, usage)}
        _span("plan", state, duration_ms=int((time.perf_counter() - start) * 1000))
        return state
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"plan failed: {exc}"}


def node_write_code(state: AgentState) -> AgentState:
    start = time.perf_counter()
    try:
        prior = ""
        for step in state.get("steps", []):
            prior += (
                f"\n--- Step {step['step_index']} code ---\n{step['code']}\n"
                f"stdout: {step.get('stdout', '')}\n"
                f"result: {json.dumps(step.get('result_json'))[:1500]}\n"
                f"error: {step.get('error')}\n"
            )
        user = (
            f"QUESTION:\n{state['question']}\n\n"
            f"PLAN:\n{state.get('plan', '')}\n\n"
            f"SCHEMA:\n{state.get('schema_context', '')}\n"
            f"{'PRIOR STEPS:' + prior if prior else ''}"
        )
        text, usage = _call_llm(user, system=_prompt("write_code"))
        code = _extract_code(text)
        state = {
            **state,
            "pending_code": code,
            "token_usage": _accumulate(state, usage),
        }
        _span("write_code", state, duration_ms=int((time.perf_counter() - start) * 1000))
        return state
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"write_code failed: {exc}"}


def node_execute_local(state: AgentState) -> AgentState:
    """Run pending code in the subprocess sandbox; persist an AnalysisStep.

    A code error is a captured (failed) step — NOT a fatal state["error"].
    Only an unexpected infra failure of the executor sets state["error"].
    """
    settings = get_settings()
    code = state.get("pending_code", "")
    step_index = state.get("current_step", 0)
    try:
        outcome = execute_code(
            code,
            state.get("dataset_paths", []),
            timeout=settings.execution_timeout_s,
        )
    except Exception as exc:  # noqa: BLE001 — genuine infra failure
        return {**state, "error": f"execute_local infra failure: {exc}"}

    step = {
        "step_index": step_index,
        "code": code,
        "stdout": outcome.get("stdout", ""),
        "result_json": outcome.get("result_json"),
        "error": outcome.get("error"),
        "duration_ms": outcome.get("duration_ms", 0),
    }

    # Persist the audit-trail row.
    try:
        with create_db_session() as session:
            session.add(
                AnalysisStep(
                    query_id=state["run_id"],
                    step_index=step_index,
                    code=code,
                    stdout=step["stdout"],
                    result_json=step["result_json"],
                    error=step["error"],
                    duration_ms=step["duration_ms"],
                )
            )
    except Exception as exc:  # noqa: BLE001
        _log.warn("audit_persist_failed", run_id=state.get("run_id"), error=str(exc))

    steps = list(state.get("steps", [])) + [step]
    new_state = {
        **state,
        "steps": steps,
        "current_step": step_index + 1,
    }
    _span(
        "execute_local",
        new_state,
        step_error=bool(step["error"]),
        duration_ms=step["duration_ms"],
    )
    return new_state


def node_reflect(state: AgentState) -> AgentState:
    start = time.perf_counter()
    steps = state.get("steps", [])
    last = steps[-1] if steps else {}
    try:
        user = (
            f"QUESTION:\n{state['question']}\n\n"
            f"PLAN:\n{state.get('plan', '')}\n\n"
            f"LATEST STEP:\ncode:\n{last.get('code', '')}\n"
            f"stdout: {last.get('stdout', '')}\n"
            f"result: {json.dumps(last.get('result_json'))[:1500]}\n"
            f"error: {last.get('error')}"
        )
        text, usage = _call_llm(user, system=_prompt("reflect"))
        done = _parse_done(text, last)
        state = {
            **state,
            "reflect_done": done,
            "token_usage": _accumulate(state, usage),
        }
        _span("reflect", state, done=done, duration_ms=int((time.perf_counter() - start) * 1000))
        return state
    except Exception:  # noqa: BLE001 — reflection failure degrades to "done"
        return {**state, "reflect_done": True}


def _parse_done(text: str, last_step: dict) -> bool:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return bool(data.get("done", False))
        except json.JSONDecodeError:
            pass
    # Fallback: done if the last step succeeded.
    return not last_step.get("error")


def node_answer(state: AgentState) -> AgentState:
    start = time.perf_counter()
    try:
        steps_summary = ""
        for step in state.get("steps", []):
            steps_summary += (
                f"\n--- Step {step['step_index']} ---\ncode:\n{step['code']}\n"
                f"stdout: {step.get('stdout', '')}\n"
                f"result: {json.dumps(step.get('result_json'))[:2000]}\n"
                f"error: {step.get('error')}\n"
            )
        user = (
            f"QUESTION:\n{state['question']}\n\n"
            f"PLAN:\n{state.get('plan', '')}\n\n"
            f"EXECUTED STEPS:{steps_summary}"
        )
        text, usage = _call_llm(user, system=_prompt("answer"))
        assumptions: list = []
        if state.get("current_step", 0) >= state.get("max_steps", 6) and not state.get("reflect_done"):
            assumptions.append("Answer produced after reaching the step limit; may be incomplete.")
        state = {
            **state,
            "answer": text.strip(),
            "shown_code": list(state.get("steps", [])),
            "assumptions": assumptions,
            "token_usage": _accumulate(state, usage),
        }
        _span("answer", state, duration_ms=int((time.perf_counter() - start) * 1000))
        return state
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"answer failed: {exc}"}


def node_finalize(state: AgentState) -> AgentState:
    _span("finalize", state)
    return {**state, "status": "completed"}


def node_handle_error(state: AgentState) -> AgentState:
    _log.error("handle_error", run_id=state.get("run_id"), error=state.get("error"))
    return {**state, "status": "failed"}
