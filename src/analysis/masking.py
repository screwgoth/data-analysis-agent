"""PII detection + masking — the ONLY sample rows that may reach the LLM.

The executor runs on raw local data; every value that could be sent to Gemini
passes through here first. Likely-PII columns are flagged in the profile and
their values are masked before any sample leaves the machine.
"""
from __future__ import annotations

import re

import pandas as pd

# Column-name heuristics (substring match, case-insensitive).
_PII_NAME_HINTS = (
    "name",
    "email",
    "e-mail",
    "phone",
    "mobile",
    "ssn",
    "social",
    "address",
    "street",
    "zip",
    "postal",
    "credit",
    "card",
    "passport",
    "dob",
    "birth",
)

_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_PHONE_RE = re.compile(r"(?:\+?\d[\s\-().]?){9,}\d")
_SSN_RE = re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b")


def _name_looks_pii(col_name: str) -> bool:
    low = str(col_name).lower()
    return any(hint in low for hint in _PII_NAME_HINTS)


def _value_looks_pii(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).head(20)
    if sample.empty:
        return False
    hits = 0
    for val in sample:
        if _EMAIL_RE.search(val) or _SSN_RE.search(val) or _PHONE_RE.fullmatch(val.strip()):
            hits += 1
    return hits >= max(1, len(sample) // 2)


def likely_pii(col_name: str, series: pd.Series) -> bool:
    """True if a column is likely to contain personally-identifiable info."""
    return _name_looks_pii(col_name) or _value_looks_pii(series)


def mask_value(value: object) -> str:
    """Irreversibly mask a single value, preserving only coarse shape."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value)
    email = _EMAIL_RE.search(text)
    if email:
        local, _, domain = email.group(0).partition("@")
        head = local[0] if local else "*"
        return f"{head}***@{domain}"
    if len(text) <= 2:
        return "*" * len(text)
    return text[0] + "*" * (len(text) - 2) + text[-1]


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _mask_cell(value: object) -> object:
    """Numbers (aggregates) pass through; strings are masked; bools/None kept."""
    if value is None or _is_number(value) or isinstance(value, bool):
        return value
    return mask_value(value)


def mask_result_feedback(result_json: object, max_records: int = 20) -> object:
    """Mask/aggregate an executed step's ``result_json`` before it re-enters an
    LLM prompt (the write_code / reflect / answer loop).

    Numeric aggregates (e.g. a groupby-sum mapping) are preserved so the model can
    reason about the answer, but raw string cell values from result rows are masked
    so no un-aggregated PII leaks back into a prompt. The FULL unmasked result is
    still persisted on the AnalysisStep audit row — only the prompt copy is masked.
    """
    # List of record dicts — the classic "raw rows" shape: summarize + mask.
    if isinstance(result_json, list):
        if not result_json:
            return {"summary": "empty result (0 rows)"}
        if all(isinstance(r, dict) for r in result_json):
            n = len(result_json)
            columns = list(result_json[0].keys())
            sample = [
                {str(k): _mask_cell(v) for k, v in rec.items()}
                for rec in result_json[:min(max_records, 5)]
            ]
            return {
                "summary": f"{n} rows",
                "columns": columns,
                "masked_sample": sample,
            }
        # List of scalars.
        return {
            "summary": f"{len(result_json)} values",
            "masked_sample": [_mask_cell(v) for v in result_json[:max_records]],
        }

    # Mapping — typically an aggregate {label: number}; keep numbers, mask strings.
    if isinstance(result_json, dict):
        masked: dict = {}
        for i, (k, v) in enumerate(result_json.items()):
            if i >= max_records:
                masked["…"] = f"({len(result_json) - max_records} more)"
                break
            masked[str(k)] = _mask_cell(v)
        return masked

    # Scalar (number/string/None).
    return _mask_cell(result_json)


def build_masked_sample(
    df: pd.DataFrame, pii_columns: list[str], n: int = 5
) -> list[dict]:
    """Return up to ``n`` rows with all PII-column values masked.

    This is the only view of the data permitted to reach the LLM.
    """
    sample = df.head(n)
    pii_set = set(pii_columns)
    rows: list[dict] = []
    for _, row in sample.iterrows():
        record: dict = {}
        for col in df.columns:
            val = row[col]
            if col in pii_set:
                record[str(col)] = mask_value(val)
            elif pd.isna(val):
                record[str(col)] = None
            else:
                record[str(col)] = val.item() if hasattr(val, "item") else val
        rows.append(record)
    return rows
