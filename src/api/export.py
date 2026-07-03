"""Export a query's result as a downloadable CSV/XLSX file (Phase 3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query as QueryParam
from fastapi.responses import Response
from sqlalchemy.orm import Session

from analysis.export import build_export
from api._common import api_error
from db.models import AnalysisStep, Query
from db.session import get_session
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.export")


@router.get("/api/queries/{query_id}/export")
def export_query(
    query_id: str,
    format: str = QueryParam(default="csv"),
    session: Session = Depends(get_session),
) -> Response:
    query = session.get(Query, query_id)
    if query is None:
        raise api_error("UNKNOWN_QUERY", f"Unknown query_id: {query_id}", 404)

    fmt = (format or "csv").lower()
    if fmt not in ("csv", "xlsx"):
        raise api_error("BAD_FORMAT", "format must be csv or xlsx", 400)

    # Use the last step that produced a result — that is the final answer's data.
    steps = (
        session.query(AnalysisStep)
        .filter(AnalysisStep.query_id == query_id)
        .order_by(AnalysisStep.step_index)
        .all()
    )
    result_json = None
    for step in steps:
        if step.result_json is not None:
            result_json = step.result_json

    try:
        data, media_type, ext = build_export(result_json, fmt)
    except ValueError as exc:
        raise api_error("BAD_FORMAT", str(exc), 400)
    except Exception as exc:  # noqa: BLE001 — build failure → 500 per contract
        _log.error("export_failed", query_id=query_id, error=str(exc))
        raise api_error("EXPORT_FAILED", f"Could not build export: {exc}", 500)

    filename = f"query-{query_id[:8]}.{ext}"
    _log.info("query_exported", query_id=query_id, format=fmt, bytes=len(data))
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
