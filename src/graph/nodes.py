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

from analysis.charting import build_chart_spec
from analysis.executor import execute_code
from analysis.masking import mask_result_feedback
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


def _call_llm(prompt: str, *, system: str, model: str | None = None) -> tuple[str, dict]:
    """Call the LLM with one retry+backoff. Raises on continued failure."""
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            return LLMClient().call_model_with_usage(prompt, system=system, model=model)
        except Exception as exc:  # noqa: BLE001 — surfaced to caller
            last_exc = exc
            if attempt == 0:
                time.sleep(1.0)
    raise RuntimeError(f"LLM call failed after retry: {last_exc}")


def _accumulate(state: AgentState, usage: dict) -> dict:
    total = dict(state.get("token_usage") or {"prompt": 0, "completion": 0, "total": 0})
    for k in ("prompt", "completion", "total"):
        total[k] = int(total.get(k, 0)) + int(usage.get(k, 0) or 0)
    # High-spend warning — total tokens across all nodes over a configured bound.
    total["warn"] = int(total.get("total", 0)) >= get_settings().token_warn_threshold
    return total


def _history_block(state: AgentState) -> str:
    """Render the most-recent N conversation turns for prompt context (Phase 2)."""
    history = state.get("history") or []
    if not history:
        return ""
    n = get_settings().history_max_turns
    recent = history[-n:]
    lines = []
    for turn in recent:
        q = str(turn.get("question", "")).strip()
        a = str(turn.get("answer", "")).strip()
        if not q:
            continue
        lines.append(f"User: {q}\nAssistant: {a}")
    if not lines:
        return ""
    return "CONVERSATION SO FAR (resolve follow-ups against this):\n" + "\n\n".join(lines)


def _masked_result(step: dict, limit: int = 1500) -> str:
    """Masked/aggregated result feedback for prompts (raw cells never leak back)."""
    return json.dumps(mask_result_feedback(step.get("result_json")))[:limit]


def _parse_plan(text: str) -> dict:
    """Plan node returns JSON {clarify, clarifying_question, plan}; degrade to text."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict) and ("plan" in data or "clarify" in data):
                return {
                    "clarify": bool(data.get("clarify", False)),
                    "clarifying_question": data.get("clarifying_question"),
                    "plan": data.get("plan") or "",
                }
        except json.JSONDecodeError:
            pass
    # Fallback: the whole response is a free-text plan.
    return {"clarify": False, "clarifying_question": None, "plan": text.strip()}


def _parse_suggestions(text: str) -> list:
    """Suggest node returns a JSON array of question strings; degrade to lines."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                out = [str(s).strip() for s in data if str(s).strip()]
                return out[:3]
        except json.JSONDecodeError:
            pass
    lines = [ln.strip(" -*0123456789.").strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln][:3]


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
        history = _history_block(state)
        join = state.get("join_context") or ""
        user = (
            (f"{history}\n\n" if history else "")
            + f"CURRENT QUESTION:\n{state['question']}\n\n"
            + (f"{join}\n\n" if join else "")
            + f"SCHEMA:\n{state.get('schema_context', '')}\n\n"
            f"PII-MASKED SAMPLE (do not trust exact masked values):\n"
            f"{state.get('masked_sample', '')}"
        )
        text, usage = _call_llm(user, system=_prompt("plan"))
        parsed = _parse_plan(text)
        new_state: AgentState = {
            **state,
            "plan": parsed.get("plan") or "",
            "token_usage": _accumulate(state, usage),
        }
        if parsed.get("clarify") and parsed.get("clarifying_question"):
            new_state["clarifying_question"] = str(parsed["clarifying_question"]).strip()
        _span(
            "plan",
            new_state,
            clarify=bool(new_state.get("clarifying_question")),
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        return new_state
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
                f"result (masked/aggregated): {_masked_result(step, 1500)}\n"
                f"error: {step.get('error')}\n"
            )
        join = state.get("join_context") or ""
        user = (
            f"QUESTION:\n{state['question']}\n\n"
            f"PLAN:\n{state.get('plan', '')}\n\n"
            + (f"{join}\n\n" if join else "")
            + f"SCHEMA:\n{state.get('schema_context', '')}\n"
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
            f"result (masked/aggregated): {_masked_result(last, 1500)}\n"
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
                f"result (masked/aggregated): {_masked_result(step, 2000)}\n"
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
        # Chart-spec + summary table derived from the last SUCCESSFUL local result
        # (never from raw data, never via the LLM). Null when not chartable.
        chart_spec = None
        for step in reversed(state.get("steps", [])):
            if not step.get("error") and step.get("result_json") is not None:
                chart_spec = build_chart_spec(step.get("result_json"))
                break
        new_state = {
            **state,
            "answer": text.strip(),
            "shown_code": list(state.get("steps", [])),
            "assumptions": assumptions,
            "chart_spec": chart_spec,
            "token_usage": _accumulate(state, usage),
        }
        _span(
            "answer",
            new_state,
            chart=bool(chart_spec),
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        return new_state
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"answer failed: {exc}"}


def node_suggest(state: AgentState) -> AgentState:
    """Produce 2-3 concrete follow-up questions (light gemini-2.5-flash).

    Degrades gracefully — a failure here yields no suggestions rather than
    failing the whole query (the answer is already produced).
    """
    start = time.perf_counter()
    try:
        user = (
            f"QUESTION:\n{state['question']}\n\n"
            f"ANSWER:\n{state.get('answer', '')}\n\n"
            f"DATASET SCHEMA (available columns — reference these):\n"
            f"{state.get('schema_context', '')}"
        )
        text, usage = _call_llm(
            user, system=_prompt("suggest"), model=get_settings().suggest_model
        )
        suggestions = _parse_suggestions(text)
        new_state = {
            **state,
            "suggestions": suggestions,
            "token_usage": _accumulate(state, usage),
        }
        _span(
            "suggest",
            new_state,
            count=len(suggestions),
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        return new_state
    except Exception as exc:  # noqa: BLE001 — degrade, never fail the answer
        _log.warn("suggest_failed", run_id=state.get("run_id"), error=str(exc))
        return {**state, "suggestions": state.get("suggestions") or []}


def node_finalize(state: AgentState) -> AgentState:
    _span("finalize", state)
    return {**state, "status": "completed"}


def node_handle_error(state: AgentState) -> AgentState:
    _log.error("handle_error", run_id=state.get("run_id"), error=state.get("error"))
    return {**state, "status": "failed"}
