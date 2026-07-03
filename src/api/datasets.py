"""Dataset upload + profiling + library CRUD.

Phase 1 shipped CSV upload. Phase 3 adds Excel (.xlsx) and PDF-table ingestion
plus the persistent library: list / fetch-one / rename / delete. Excel and PDF
uploads are normalized to a canonical local CSV so the subprocess executor keeps
reading local data unchanged.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from analysis.ingest import load_excel, load_pdf
from analysis.profiler import profile_loaded, store_canonical_csv, store_csv, profile_csv
from api._common import ok, api_error
from config.settings import get_settings
from db.models import Dataset, DatasetProfile
from db.session import get_session
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.datasets")

_SUPPORTED = (".csv", ".xlsx", ".pdf")


class RenameRequest(BaseModel):
    name: str


@router.post("/api/datasets")
async def create_dataset(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> dict:
    settings = get_settings()
    filename = file.filename or "dataset.csv"
    lower = filename.lower()
    ext = next((e for e in _SUPPORTED if lower.endswith(e)), None)
    if ext is None:
        raise api_error(
            "UNSUPPORTED_FORMAT",
            "Supported formats: .csv, .xlsx, .pdf",
            400,
        )

    contents = await file.read()
    if len(contents) > settings.max_upload_bytes:
        raise api_error("FILE_TOO_LARGE", "File exceeds the ~100MB limit", 413)

    source_format = {".csv": "csv", ".xlsx": "xlsx", ".pdf": "pdf"}[ext]
    dataset = Dataset(
        name=name or filename,
        filename=filename,
        source_format=source_format,
        local_path="",
    )
    session.add(dataset)
    session.flush()

    try:
        if ext == ".csv":
            path = store_csv(contents, dataset.id, filename, settings.data_dir)
            profile = profile_csv(path)
        else:
            df = load_excel(contents) if ext == ".xlsx" else load_pdf(contents)
            # Keep the original upload for provenance, plus a canonical CSV the
            # executor reads.
            store_csv(contents, dataset.id, filename, settings.data_dir)
            path = store_canonical_csv(df, dataset.id, settings.data_dir)
            profile = profile_loaded(df)
    except ValueError as exc:
        _log.warn("parse_failed", filename=filename, error=str(exc))
        raise api_error("UNPARSEABLE_FILE", str(exc), 400)
    except Exception as exc:  # noqa: BLE001 — unexpected parse crash → clean 400
        _log.warn("parse_failed", filename=filename, error=str(exc))
        raise api_error("UNPARSEABLE_FILE", f"Could not parse {source_format} file: {exc}", 400)

    dataset.local_path = str(path)
    dataset.row_count = profile["row_count"]
    dataset.col_count = profile["col_count"]
    dataset.masked_sample = profile["masked_sample"]
    session.add(DatasetProfile(dataset_id=dataset.id, columns=profile["columns"]))
    session.flush()

    _log.info(
        "dataset_created",
        dataset_id=dataset.id,
        format=source_format,
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


@router.get("/api/datasets")
def list_datasets(session: Session = Depends(get_session)) -> dict:
    rows = session.query(Dataset).order_by(Dataset.created_at.desc()).all()
    return ok(
        [
            {
                "id": d.id,
                "name": d.name,
                "source_format": d.source_format,
                "row_count": d.row_count,
                "col_count": d.col_count,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in rows
        ]
    )


@router.get("/api/datasets/{dataset_id}")
def get_dataset(dataset_id: str, session: Session = Depends(get_session)) -> dict:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise api_error("UNKNOWN_DATASET", f"Unknown dataset_id: {dataset_id}", 404)
    profile = (
        session.query(DatasetProfile)
        .filter(DatasetProfile.dataset_id == dataset_id)
        .first()
    )
    return ok(
        {
            "id": dataset.id,
            "name": dataset.name,
            "source_format": dataset.source_format,
            "row_count": dataset.row_count,
            "col_count": dataset.col_count,
            "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
            "profile": {"columns": (profile.columns if profile else []) or []},
        }
    )


@router.patch("/api/datasets/{dataset_id}")
def rename_dataset(
    dataset_id: str,
    req: RenameRequest,
    session: Session = Depends(get_session),
) -> dict:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise api_error("UNKNOWN_DATASET", f"Unknown dataset_id: {dataset_id}", 404)
    new_name = (req.name or "").strip()
    if not new_name:
        raise api_error("INVALID_NAME", "A non-empty name is required", 400)
    dataset.name = new_name
    session.flush()
    _log.info("dataset_renamed", dataset_id=dataset_id, name=new_name)
    return ok({"id": dataset.id, "name": dataset.name})


@router.delete("/api/datasets/{dataset_id}")
def delete_dataset(dataset_id: str, session: Session = Depends(get_session)) -> dict:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise api_error("UNKNOWN_DATASET", f"Unknown dataset_id: {dataset_id}", 404)

    settings = get_settings()
    # Remove the whole per-dataset directory (original upload + canonical CSV).
    dataset_dir = Path(settings.data_dir) / "datasets" / dataset_id
    if dataset_dir.exists():
        shutil.rmtree(dataset_dir, ignore_errors=True)
    elif dataset.local_path:
        # Fallback: remove the single tracked file if the dir layout differs.
        p = Path(dataset.local_path)
        if p.exists():
            try:
                p.unlink()
            except OSError as exc:  # Windows-safe — never 500 on a locked file
                _log.warn("file_delete_failed", dataset_id=dataset_id, error=str(exc))

    session.query(DatasetProfile).filter(
        DatasetProfile.dataset_id == dataset_id
    ).delete()
    session.delete(dataset)
    session.flush()
    _log.info("dataset_deleted", dataset_id=dataset_id)
    return ok({"id": dataset_id, "deleted": True})
