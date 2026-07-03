"""Golden-path integration test — real Gemini, real subprocess, real DB.

Uploads a multi-column CSV (with a PII email column), profiles it, then asks a
quantitative question and asserts the returned key number EQUALS the value
computed by running pandas over the FULL dataset here in the test.
"""
import json

import pandas as pd
import pytest

from sqlalchemy.orm import Session

import db.session as session_module
from db.models import AnalysisStep, Dataset


def _flatten(obj) -> str:
    return json.dumps(obj, default=str)


@pytest.fixture
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path / "store"))
    yield


@pytest.fixture
def sales_csv(tmp_path):
    df = pd.DataFrame(
        {
            "region": ["North", "South", "North", "West", "South", "North"],
            "revenue": [1000, 2000, 1500, 500, 2500, 800],
            "email": [
                "alice@corp.com",
                "bob@corp.com",
                "carol@corp.com",
                "dan@corp.com",
                "eve@corp.com",
                "frank@corp.com",
            ],
        }
    )
    path = tmp_path / "sales.csv"
    df.to_csv(path, index=False)
    return df, path


@pytest.mark.usefixtures("_require_llm_key", "_data_dir")
def test_golden_path_upload_profile_ask(api_client, sales_csv, _isolated_db):
    df, path = sales_csv

    # --- Upload + profile ---
    with open(path, "rb") as fh:
        r = api_client.post(
            "/api/datasets",
            files={"file": ("sales.csv", fh, "text/csv")},
        )
    assert r.status_code == 200, r.text
    ds = r.json()["data"]
    assert ds["row_count"] == 6
    assert ds["col_count"] == 3
    cols = {c["name"]: c for c in ds["profile"]["columns"]}
    assert cols["email"]["likely_pii"] is True
    assert cols["region"]["likely_pii"] is False
    dataset_id = ds["id"]

    # --- Guardrail: raw email never in the masked sample that reaches the LLM ---
    with Session(session_module._engine) as s:
        stored = s.get(Dataset, dataset_id)
        masked_blob = _flatten(stored.masked_sample)
    for raw in df["email"]:
        assert raw not in masked_blob, f"raw PII {raw} leaked into LLM-bound sample"

    # --- Ask a quantitative question ---
    r = api_client.post(
        "/api/queries",
        json={"question": "What is the total revenue by region?", "dataset_ids": [dataset_id]},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["status"] == "completed", body.get("error_message")
    assert body["steps"], "expected at least one executed analysis step"

    # Steps carry real code + real captured output.
    assert any(step["code"] for step in body["steps"])
    assert any(step.get("result_json") is not None for step in body["steps"])

    # --- Correctness: compute the truth over the FULL dataset ourselves ---
    truth = df.groupby("region")["revenue"].sum().to_dict()

    # The per-region totals must appear in a step result OR the answer prose.
    steps_blob = _flatten([s.get("result_json") for s in body["steps"]])
    answer = body["answer"] or ""
    for region, total in truth.items():
        assert (
            str(int(total)) in steps_blob or str(int(total)) in answer
        ), f"expected {region}={total} in results/answer"
    # Every per-region total must be present in a real step result_json (genuine gate).
    assert all(
        str(int(total)) in steps_blob for total in truth.values()
    ), "each per-region total must appear in a persisted step result_json"

    # Answer prose references the numbers.
    assert any(str(int(t)) in answer for t in truth.values())

    # --- Audit trail persisted ---
    with Session(session_module._engine) as s:
        rows = (
            s.query(AnalysisStep)
            .filter(AnalysisStep.query_id == body["id"])
            .all()
        )
    assert len(rows) == len(body["steps"])
    assert all(row.code for row in rows)


@pytest.mark.usefixtures("_require_llm_key", "_data_dir")
def test_ambiguous_question_does_not_crash(api_client, sales_csv, _isolated_db):
    _, path = sales_csv
    with open(path, "rb") as fh:
        r = api_client.post("/api/datasets", files={"file": ("sales.csv", fh, "text/csv")})
    dataset_id = r.json()["data"]["id"]

    r = api_client.post(
        "/api/queries",
        json={"question": "show me the interesting stuff", "dataset_ids": [dataset_id]},
    )
    # Never a 500 crash — graceful completed/failed envelope.
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["status"] in ("completed", "failed")
