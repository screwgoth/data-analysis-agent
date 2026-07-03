"""Join-key proposal for multi-dataset (cross-file) analysis.

Given the per-column profile info of two or more selected datasets, propose the
most likely column to join/merge on: a column name shared by ALL datasets whose
dtype family is compatible across them. Deterministic and offline — no LLM, no
raw data. When nothing overlaps confidently we return ``None`` so the agent can
ask a clarifying question or state its assumption instead of guessing.
"""
from __future__ import annotations


def _dtype_family(dtype: object) -> str:
    """Coarse dtype family so ``int64`` and ``Int32`` (etc.) count as compatible."""
    d = str(dtype or "").lower()
    if "bool" in d:
        return "bool"
    if any(tok in d for tok in ("int", "float", "double", "number", "decimal")):
        return "numeric"
    if any(tok in d for tok in ("datetime", "timestamp", "date", "time")):
        return "datetime"
    return "text"


def _key_score(key: str) -> int:
    """Rank id/key-like columns higher — they are the usual join columns."""
    score = 0
    if key == "id" or key.endswith("_id") or key.endswith("id"):
        score += 10
    if "key" in key or "code" in key or "uuid" in key:
        score += 5
    return score


def propose_join_key(profiles: list[list[dict]]) -> str | None:
    """Propose a join key across ``profiles`` (one column-info list per dataset).

    Each column-info dict is expected to carry at least ``name`` and ``dtype``
    (the shape stored on ``DatasetProfile.columns``). Returns the original-case
    column name shared by every dataset with a compatible dtype family, or
    ``None`` when there is no confident shared key.
    """
    if not profiles or len(profiles) < 2:
        return None

    col_maps: list[dict[str, tuple[str, str]]] = []
    for cols in profiles:
        mapping: dict[str, tuple[str, str]] = {}
        for col in cols or []:
            name = col.get("name")
            if name is None:
                continue
            key = str(name).strip().lower()
            if not key:
                continue
            mapping[key] = (str(name), _dtype_family(col.get("dtype")))
        col_maps.append(mapping)

    if any(not m for m in col_maps):
        return None

    # Column names present in EVERY dataset.
    common = set(col_maps[0])
    for mapping in col_maps[1:]:
        common &= set(mapping)
    if not common:
        return None

    # Keep only those whose dtype family agrees across all datasets.
    candidates = [
        key
        for key in common
        if len({m[key][1] for m in col_maps}) == 1
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda k: (-_key_score(k), k))
    best = candidates[0]
    return col_maps[0][best][0]
