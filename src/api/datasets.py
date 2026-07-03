"""Dataset upload + profiling endpoint (Phase 1: CSV only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from analysis.profiler import profile_csv, store_csv
from api._common import ok, api_error
from config.settings import get_settings
from db.models import Dataset, DatasetProfile
from db.session import get_session
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.datasets")


@router.post("/api/datasets")
async def create_dataset(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> dict:
    settings = get_settings()
    filename = file.filename or "dataset.csv"
    if not filename.lower().endswith(".csv"):
        raise api_error("UNSUPPORTED_FORMAT", "Phase 1 supports CSV files only", 400)

    contents = await file.read()
    if len(contents) > settings.max_upload_bytes:
        raise api_error("FILE_TOO_LARGE", "File exceeds the ~100MB limit", 413)

    dataset = Dataset(
        name=name or filename,
        filename=filename,
        source_format="csv",
        local_path="",
    )
    session.add(dataset)
    session.flush()

    path = store_csv(contents, dataset.id, filename, settings.data_dir)
    dataset.local_path = str(path)

    try:
        profile = profile_csv(path)
    except Exception as exc:  # noqa: BLE001 — unparseable CSV
        _log.warn("profile_failed", filename=filename, error=str(exc))
        raise api_error("UNPARSEABLE_FILE", f"Could not parse CSV: {exc}", 400)

    dataset.row_count = profile["row_count"]
    dataset.col_count = profile["col_count"]
    dataset.masked_sample = profile["masked_sample"]
    session.add(
        DatasetProfile(dataset_id=dataset.id, columns=profile["columns"])
    )
    session.flush()

    _log.info(
        "dataset_created",
        dataset_id=dataset.id,
        rows=dataset.row_count,
        cols=dataset.col_count,
    )
    return ok(
        {
            "id": dataset.id,
            "name": dataset.name,
            "row_count": dataset.row_count,
            "col_count": dataset.col_count,
            "profile": {"columns": profile["columns"]},
        }
    )
