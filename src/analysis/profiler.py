"""CSV ingestion + auto-profiling.

Stores the raw uploaded file locally under ``data/datasets/<id>/`` (gitignored),
reads it with pandas, and computes a per-column profile plus a PII-masked sample.
Raw values never leave the machine — only the profile + masked sample can reach
the LLM.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from analysis.masking import build_masked_sample, likely_pii


def _dtype_label(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    return "string"


def profile_dataframe(df: pd.DataFrame) -> dict:
    """Compute the per-column profile and a PII-masked sample."""
    columns: list[dict] = []
    pii_columns: list[str] = []
    for col in df.columns:
        series = df[col]
        dtype = _dtype_label(series)
        is_pii = likely_pii(col, series)
        if is_pii:
            pii_columns.append(str(col))
        info: dict = {
            "name": str(col),
            "dtype": dtype,
            "missing_count": int(series.isna().sum()),
            "distinct_count": int(series.nunique(dropna=True)),
            "likely_pii": bool(is_pii),
        }
        if dtype in ("integer", "float") and series.notna().any():
            col_min = series.min()
            col_max = series.max()
            info["min"] = _to_scalar(col_min)
            info["max"] = _to_scalar(col_max)
            info["mean"] = _to_scalar(series.mean())
            try:
                info["range"] = _to_scalar(col_max - col_min)
            except Exception:
                info["range"] = None
        columns.append(info)

    masked_sample = build_masked_sample(df, pii_columns, n=5)
    return {"columns": columns, "masked_sample": masked_sample}


def _to_scalar(value: object):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return value.item() if hasattr(value, "item") else value


def profile_loaded(df: pd.DataFrame) -> dict:
    """Profile an already-loaded DataFrame (from CSV, Excel, or PDF).

    Returns row/col counts, per-column profile, and the PII-masked sample —
    the shape the upload endpoint persists onto the ``Dataset`` row.
    """
    profile = profile_dataframe(df)
    return {
        "row_count": int(len(df)),
        "col_count": int(len(df.columns)),
        "columns": profile["columns"],
        "masked_sample": profile["masked_sample"],
    }


def profile_csv(path: str | Path) -> dict:
    """Read a stored CSV and return row/col counts, profile, and masked sample."""
    return profile_loaded(pd.read_csv(path))


def store_canonical_csv(df: pd.DataFrame, dataset_id: str, data_dir: str | Path) -> Path:
    """Persist a normalized ``data.csv`` under data/datasets/<id>/.

    Excel/PDF uploads are normalized to a canonical CSV so the subprocess
    executor (which only reads CSV) keeps reading local data unchanged.
    """
    dest_dir = Path(data_dir) / "datasets" / dataset_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "data.csv"
    df.to_csv(dest, index=False)
    return dest


def store_csv(file_bytes: bytes, dataset_id: str, filename: str, data_dir: str | Path) -> Path:
    """Persist raw upload bytes under data/datasets/<id>/<filename>."""
    dest_dir = Path(data_dir) / "datasets" / dataset_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(file_bytes)
    return dest
