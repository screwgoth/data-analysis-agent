"""Excel (.xlsx) ingestion.

Reads the workbook with pandas (openpyxl engine). When a workbook has multiple
sheets we ingest the FIRST sheet only (``sheet_name=0``) — a single dataset maps
to a single table, and the first sheet is the conventional primary sheet. A
future enhancement could let the user pick a named sheet.
"""
from __future__ import annotations

import io

import pandas as pd


def load_excel(file_bytes: bytes) -> pd.DataFrame:
    """Parse .xlsx bytes into a DataFrame (first sheet).

    Raises ``ValueError`` if the workbook cannot be parsed or is empty.
    """
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001 — surface as a clean 400
        raise ValueError(f"Could not parse Excel file: {exc}") from exc

    if df is None or df.shape[1] == 0:
        raise ValueError("Excel file contains no tabular data")
    return df
