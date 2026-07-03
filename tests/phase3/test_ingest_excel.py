"""Excel (.xlsx) ingestion — real file through the upload endpoint (no LLM)."""
import io

import pandas as pd

from analysis.ingest import load_excel


def _sales_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "region": ["North", "South", "West"],
            "revenue": [100.0, 250.5, 300.0],
            "units": [1, 3, 4],
        }
    )


def _xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    return buf.getvalue()


def test_load_excel_first_sheet():
    df = load_excel(_xlsx_bytes(_sales_df()))
    assert list(df.columns) == ["region", "revenue", "units"]
    assert len(df) == 3


def test_load_excel_unparseable_raises():
    import pytest

    with pytest.raises(ValueError):
        load_excel(b"this is not an xlsx file")


def test_upload_xlsx_profiles_and_counts(api_client):
    df = _sales_df()
    files = {
        "file": (
            "sales.xlsx",
            _xlsx_bytes(df),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    resp = api_client.post("/api/datasets", files=files)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["row_count"] == 3
    assert data["col_count"] == 3
    col_names = {c["name"] for c in data["profile"]["columns"]}
    assert col_names == {"region", "revenue", "units"}


def test_upload_multi_sheet_takes_first(api_client):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        _sales_df().to_excel(writer, index=False, sheet_name="Primary")
        pd.DataFrame({"other": [1, 2]}).to_excel(writer, index=False, sheet_name="Second")
    files = {"file": ("multi.xlsx", buf.getvalue(),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = api_client.post("/api/datasets", files=files)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # First sheet has 3 cols; second has 1 — confirm we took the first.
    assert data["col_count"] == 3
