"""Session endpoints (Phase 2) — create a conversation over dataset(s) and
fetch its ordered Query history."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.models import AnalysisSession, Dataset, Query
from db.session import get_session
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.sessions")


class SessionRequest(BaseModel):
    dataset_ids: list[str]


def _validate_datasets(dataset_ids: list[str], session: Session) -> None:
    if not dataset_ids:
        raise api_error("MISSING_DATASET", "At least one dataset_id is required", 400)
    for did in dataset_ids:
        if session.get(Dataset, did) is None:
            raise api_error("UNKNOWN_DATASET", f"Unknown dataset_id: {did}", 400)


@router.post("/api/sessions")
def create_session(req: SessionRequest, session: Session = Depends(get_session)) -> dict:
    _validate_datasets(req.dataset_ids, session)
    row = AnalysisSession(dataset_ids=list(req.dataset_ids))
    session.add(row)
    session.flush()
    _log.info("session_created", session_id=row.id, datasets=len(req.dataset_ids))
    return ok(
        {
            "id": row.id,
            "dataset_ids": row.dataset_ids,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
    )


@router.get("/api/sessions/{session_id}")
def get_session_history(session_id: str, session: Session = Depends(get_session)) -> dict:
    row = session.get(AnalysisSession, session_id)
    if row is None:
        raise api_error("NOT_FOUND", f"Unknown session: {session_id}", 404)

    queries = (
        session.query(Query)
        .filter(Query.session_id == session_id)
        .order_by(Query.created_at)
        .all()
    )
    return ok(
        {
            "id": row.id,
            "dataset_ids": row.dataset_ids,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "queries": [
                {
                    "id": q.id,
                    "question": q.question,
                    "answer": q.answer,
                    "clarifying_question": q.clarifying_question,
                    "chart_spec": q.chart_spec,
                    "suggestions": q.suggestions or [],
                    "token_usage": q.token_usage
                    or {"prompt": 0, "completion": 0, "total": 0, "warn": False},
                    "status": q.status,
                    "created_at": q.created_at.isoformat() if q.created_at else None,
                }
                for q in queries
            ],
        }
    )
