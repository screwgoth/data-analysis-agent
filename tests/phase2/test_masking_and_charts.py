"""Unit tests (no LLM) for the Phase-2 privacy + chart helpers.

- result-feedback masking: raw string cell values are masked before a result can
  re-enter an LLM prompt, while numeric aggregates pass through intact.
- chart-spec: a breakdown result yields a well-formed spec; a scalar yields None.
"""
import json

from analysis.charting import build_chart_spec
from analysis.masking import mask_result_feedback


def test_raw_cell_values_are_masked_in_feedback():
    # A result shaped like raw rows containing PII.
    raw_rows = [
        {"name": "Alice Smith", "email": "alice@corp.com", "revenue": 1000},
        {"name": "Bob Jones", "email": "bob@corp.com", "revenue": 2000},
    ]
    masked = mask_result_feedback(raw_rows)
    blob = json.dumps(masked)

    # No raw PII cell value survives into the prompt-bound feedback.
    assert "alice@corp.com" not in blob
    assert "bob@corp.com" not in blob
    assert "Alice Smith" not in blob
    assert "Bob Jones" not in blob
    # It is summarized to shape, not the full raw rows.
    assert masked["summary"].startswith("2 rows")
    assert "email" in masked["columns"]


def test_numeric_aggregates_pass_through_for_reasoning():
    # A groupby-sum mapping — the model must still see these numbers.
    agg = {"North": 3300, "South": 4500, "West": 500}
    masked = mask_result_feedback(agg)
    assert masked == agg  # numbers preserved, no keys/values mangled


def test_string_keys_kept_but_string_values_masked_in_mapping():
    mapping = {"top_customer": "Alice Smith"}
    masked = mask_result_feedback(mapping)
    assert "top_customer" in masked
    assert masked["top_customer"] != "Alice Smith"  # value masked


def test_chart_spec_from_breakdown_mapping():
    result = {"North": 3300, "South": 4500, "West": 500}
    spec = build_chart_spec(result)
    assert spec is not None
    assert spec["type"] == "bar"
    assert spec["x"] == ["North", "South", "West"]
    assert spec["series"][0]["data"] == [3300, 4500, 500]
    assert spec["table"]["columns"] == ["category", "value"]
    assert len(spec["table"]["rows"]) == 3


def test_chart_spec_from_records():
    result = [
        {"month": "Jan", "sales": 100},
        {"month": "Feb", "sales": 200},
        {"month": "Mar", "sales": 150},
    ]
    spec = build_chart_spec(result)
    assert spec is not None
    assert spec["type"] == "bar"
    assert spec["y_label"] == "sales"
    assert spec["series"][0]["data"] == [100, 200, 150]


def test_chart_spec_none_for_scalar():
    assert build_chart_spec(8300) is None
    assert build_chart_spec("a prose answer") is None
    assert build_chart_spec({"only_one": 5}) is None  # single point, not a breakdown
