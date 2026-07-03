"""Deterministic chart-spec + summary-table builder (Phase 2).

Charts are derived from the LOCALLY-computed result of an analysis step — never
from raw data and never via the LLM (spec/agent.md: `build_chart` has no LLM,
no side-effects). Returns ``None`` when the result is not chartable (e.g. a scalar
answer), so ``chart_spec`` stays null for non-trending answers.
"""
from __future__ import annotations


def _num(value: object) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            f = float(value)
        except ValueError:
            return None
        return int(f) if f.is_integer() else f
    return None


def build_chart_spec(result_json: object, max_points: int = 50) -> dict | None:
    """Build a bar chart-spec + summary table from a step result, or None.

    Chartable shapes:
      - a mapping {label: number}  (e.g. groupby-sum)  -> categorical bar
      - a list of record dicts with ≥1 label col + ≥1 numeric col -> bar
    """
    # Mapping of label -> number.
    if isinstance(result_json, dict) and result_json:
        labels: list[str] = []
        values: list = []
        for k, v in result_json.items():
            num = _num(v)
            if num is None:
                return None  # not a clean numeric breakdown
            labels.append(str(k))
            values.append(num)
        if len(labels) < 2:
            return None
        labels, values = labels[:max_points], values[:max_points]
        return {
            "type": "bar",
            "x": labels,
            "x_label": "category",
            "y_label": "value",
            "series": [{"name": "value", "data": values}],
            "table": {
                "columns": ["category", "value"],
                "rows": [[l, v] for l, v in zip(labels, values)],
            },
        }

    # List of record dicts.
    if (
        isinstance(result_json, list)
        and len(result_json) >= 2
        and all(isinstance(r, dict) for r in result_json)
    ):
        keys = list(result_json[0].keys())
        if len(keys) < 2:
            return None
        numeric_cols = [
            k for k in keys if all(_num(r.get(k)) is not None for r in result_json)
        ]
        label_cols = [k for k in keys if k not in numeric_cols]
        if not numeric_cols or not label_cols:
            return None
        x_col = label_cols[0]
        y_col = numeric_cols[0]
        rows = result_json[:max_points]
        x = [str(r.get(x_col)) for r in rows]
        data = [_num(r.get(y_col)) for r in rows]
        return {
            "type": "bar",
            "x": x,
            "x_label": x_col,
            "y_label": y_col,
            "series": [{"name": y_col, "data": data}],
            "table": {
                "columns": keys,
                "rows": [[r.get(k) for k in keys] for r in rows],
            },
        }

    return None
