"""Query endpoint — runs the analysis graph synchronously and returns the answer."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.models import Dataset
from db.session import get_session
from graph.runner import load_query_response, run_query
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.queries")


class QueryRequest(BaseModel):
    question: str
    dataset_ids: list[str]
    session_id: str | None = None


@router.post("/api/queries")
def create_query(req: QueryRequest, session: Session = Depends(get_session)) -> dict:
    if not req.question or not req.question.strip():
        raise api_error("MISSING_QUESTION", "A question is required", 400)
    if not req.dataset_ids:
        raise api_error("MISSING_DATASET", "At least one dataset_id is required", 400)
    for did in req.dataset_ids:
        if session.get(Dataset, did) is None:
            raise api_error("UNKNOWN_DATASET", f"Unknown dataset_id: {did}", 400)

    run_id = run_query(req.question, req.dataset_ids, req.session_id)
    response = load_query_response(run_id)
    if not response:
        raise api_error("NOT_FOUND", "Query not found after run", 500)

    if response.get("status") == "failed":
        _log.error("query_failed", run_id=run_id, error=response.get("error_message"))
    return ok(response)
