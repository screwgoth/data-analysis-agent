"""Run a Query end-to-end: build state from the DB, invoke the graph, persist."""
from __future__ import annotations

import json

from config.settings import get_settings
from db.models import AnalysisStep, Dataset, DatasetProfile, Query
from db.session import create_db_session, init_db
from graph.agent import agentic_ai
from graph.state import AgentState
from observability.events import get_logger

_log = get_logger("runner")


def _schema_context(profile: DatasetProfile | None, dataset: Dataset) -> str:
    lines = [f"Dataset '{dataset.name}': {dataset.row_count} rows, {dataset.col_count} columns."]
    cols = (profile.columns if profile else None) or []
    for col in cols:
        parts = [f"- {col['name']} ({col.get('dtype')})"]
        parts.append(f"missing={col.get('missing_count')}")
        parts.append(f"distinct={col.get('distinct_count')}")
        if "min" in col:
            parts.append(f"min={col.get('min')} max={col.get('max')} mean={col.get('mean')}")
        if col.get("likely_pii"):
            parts.append("[likely_pii — masked]")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def run_query(question: str, dataset_ids: list[str], session_id: str | None = None) -> str:
    """Create a Query, run the analysis graph synchronously, persist, return id."""
    init_db()
    settings = get_settings()

    with create_db_session() as session:
        query = Query(
            question=question,
            dataset_ids=list(dataset_ids),
            session_id=session_id,
            status="pending",
        )
        session.add(query)
        session.flush()
        run_id = query.id

        datasets = [session.get(Dataset, did) for did in dataset_ids]
        datasets = [d for d in datasets if d is not None]
        schema_parts: list[str] = []
        masked_parts: list[str] = []
        dataset_paths: list[str] = []
        for ds in datasets:
            profile = (
                session.query(DatasetProfile)
                .filter(DatasetProfile.dataset_id == ds.id)
                .first()
            )
            schema_parts.append(_schema_context(profile, ds))
            masked_parts.append(json.dumps(ds.masked_sample or [])[:4000])
            dataset_paths.append(ds.local_path)

    initial: AgentState = {
        "run_id": run_id,
        "session_id": session_id,
        "question": question,
        "dataset_ids": list(dataset_ids),
        "dataset_paths": dataset_paths,
        "schema_context": "\n\n".join(schema_parts),
        "masked_sample": "\n\n".join(masked_parts),
        "history": [],
        "steps": [],
        "current_step": 0,
        "max_steps": settings.max_steps,
        "token_usage": {"prompt": 0, "completion": 0, "total": 0, "warn": False},
        "error": None,
    }

    _log.info("query_start", run_id=run_id, datasets=len(dataset_paths))
    final = agentic_ai.invoke(initial, {"recursion_limit": 50})
    _log.info(
        "query_done",
        run_id=run_id,
        status=final.get("status"),
        steps=len(final.get("steps", [])),
        tokens=(final.get("token_usage") or {}).get("total"),
    )

    with create_db_session() as session:
        query = session.get(Query, run_id)
        query.status = final.get("status", "completed")
        query.plan = final.get("plan")
        query.answer = final.get("answer")
        query.assumptions = final.get("assumptions") or []
        query.clarifying_question = final.get("clarifying_question")
        query.chart_spec = final.get("chart_spec")
        query.suggestions = final.get("suggestions") or []
        query.token_usage = final.get("token_usage") or {}
        query.error_message = final.get("error")

    return run_id


def load_query_response(run_id: str) -> dict:
    """Assemble the API response envelope for a completed/failed query."""
    with create_db_session() as session:
        query = session.get(Query, run_id)
        if query is None:
            return {}
        steps = (
            session.query(AnalysisStep)
            .filter(AnalysisStep.query_id == run_id)
            .order_by(AnalysisStep.step_index)
            .all()
        )
        return {
            "id": query.id,
            "status": query.status,
            "answer": query.answer,
            "assumptions": query.assumptions or [],
            "clarifying_question": query.clarifying_question,
            "steps": [
                {
                    "step_index": s.step_index,
                    "code": s.code,
                    "stdout": s.stdout,
                    "result_json": s.result_json,
                    "error": s.error,
                    "duration_ms": s.duration_ms,
                }
                for s in steps
            ],
            "chart_spec": query.chart_spec,
            "suggestions": query.suggestions or [],
            "token_usage": query.token_usage or {"prompt": 0, "completion": 0, "total": 0, "warn": False},
            "error_message": query.error_message,
        }
