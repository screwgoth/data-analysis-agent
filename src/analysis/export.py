"""Build downloadable export bytes from a query's persisted result.

The final ``AnalysisStep.result_json`` holds the analysis result the user saw
(records, a single object, or a scalar). We coerce it into a DataFrame and
serialize to CSV or XLSX. All bytes are built locally from persisted results —
no LLM call, no raw-data transfer.
"""
from __future__ import annotations

import io

import pandas as pd


def result_to_dataframe(result_json: object) -> pd.DataFrame:
    """Coerce a persisted result_json into a DataFrame for export."""
    if result_json is None:
        return pd.DataFrame()
    if isinstance(result_json, list):
        if result_json and isinstance(result_json[0], dict):
            return pd.DataFrame(result_json)
        return pd.DataFrame({"value": result_json})
    if isinstance(result_json, dict):
        # A groupby/Series-like {key: value} map, or a single record.
        if result_json and all(not isinstance(v, (dict, list)) for v in result_json.values()):
            return pd.DataFrame(
                {"key": list(result_json.keys()), "value": list(result_json.values())}
            )
        return pd.DataFrame([result_json])
    # Scalar (int/float/str/bool).
    return pd.DataFrame({"value": [result_json]})


def build_export(result_json: object, fmt: str) -> tuple[bytes, str, str]:
    """Return ``(bytes, media_type, extension)`` for the given format.

    Raises ``ValueError`` for an unsupported format.
    """
    df = result_to_dataframe(result_json)
    fmt = (fmt or "csv").lower()
    if fmt == "csv":
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        return buf.getvalue().encode("utf-8"), "text/csv", "csv"
    if fmt == "xlsx":
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="result")
        return (
            buf.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xlsx",
        )
    raise ValueError(f"Unsupported export format: {fmt}")
