"""Phase-2 integration tests — real Gemini via .env, real subprocess, real DB.

Covers the hard cases: follow-up resolution against history, clarify-on-ambiguity,
grounded follow-up suggestions, chart-spec from local results, and token accounting
with a high-spend warning.
"""
import json

import pandas as pd
import pytest


def _flatten(obj) -> str:
    return json.dumps(obj, default=str)


@pytest.fixture
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path / "store"))
    yield


@pytest.fixture
def sales_df():
    # 2024 by-month means are clean integers (Jan=150, Feb=400); 2023 rows exist
    # so a correctly-scoped "just for 2024" answer differs from the full-data one.
    return pd.DataFrame(
        {
            "month": ["Jan", "Jan", "Feb", "Feb", "Jan", "Feb"],
            "year": [2024, 2024, 2024, 2024, 2023, 2023],
            "region": ["North", "South", "North", "South", "North", "South"],
            "sales": [100, 200, 300, 500, 999, 777],
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


def _upload(api_client, df, name="sales.csv"):
    csv = df.to_csv(index=False).encode()
    r = api_client.post("/api/datasets", files={"file": (name, csv, "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


def _new_session(api_client, dataset_id):
    r = api_client.post("/api/sessions", json={"dataset_ids": [dataset_id]})
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


def _ask(api_client, dataset_id, question, session_id):
    r = api_client.post(
        "/api/queries",
        json={"question": question, "dataset_ids": [dataset_id], "session_id": session_id},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.usefixtures("_require_llm_key", "_data_dir")
def test_followup_resolves_against_history(api_client, sales_df):
    dataset_id = _upload(api_client, sales_df)
    session_id = _new_session(api_client, dataset_id)

    # First turn establishes "average sales by month".
    first = _ask(api_client, dataset_id, "What is the average sales by month?", session_id)
    assert first["status"] == "completed", first.get("error_message")

    # Follow-up does NOT restate "sales by month" — must resolve from history.
    second = _ask(api_client, dataset_id, "and just for 2024?", session_id)
    assert second["status"] == "completed", second.get("error_message")

    # Truth: average sales by month over the 2024 subset (Jan=150, Feb=400).
    truth = (
        sales_df[sales_df["year"] == 2024]
        .groupby("month")["sales"]
        .mean()
        .to_dict()
    )
    assert truth == {"Jan": 150.0, "Feb": 400.0}

    steps_blob = _flatten([s.get("result_json") for s in second["steps"]])
    answer = second["answer"] or ""
    for month, mean in truth.items():
        assert (
            str(int(mean)) in steps_blob or str(int(mean)) in answer
        ), f"expected 2024 {month} mean={mean} in scoped follow-up result/answer"

    # Persisted under the session; history readable back.
    hist = api_client.get(f"/api/sessions/{session_id}").json()["data"]
    assert len(hist["queries"]) == 2


@pytest.mark.usefixtures("_require_llm_key", "_data_dir")
def test_ambiguous_question_asks_instead_of_guessing(api_client, sales_df):
    dataset_id = _upload(api_client, sales_df)
    session_id = _new_session(api_client, dataset_id)

    body = _ask(api_client, dataset_id, "show me the top ones", session_id)
    assert body["status"] == "completed", body.get("error_message")
    assert body["clarifying_question"], "expected a clarifying question for an ambiguous ask"
    # It clarified instead of fabricating an analysis — no code ran.
    assert not body["steps"], "no analysis steps should run when clarifying"


@pytest.mark.usefixtures("_require_llm_key", "_data_dir")
def test_answer_returns_grounded_suggestions(api_client, sales_df):
    dataset_id = _upload(api_client, sales_df)
    session_id = _new_session(api_client, dataset_id)

    body = _ask(api_client, dataset_id, "What is the total sales by region?", session_id)
    assert body["status"] == "completed", body.get("error_message")

    suggestions = body["suggestions"]
    assert 2 <= len(suggestions) <= 3, suggestions
    assert all(isinstance(s, str) and s.strip() for s in suggestions)

    real_cols = {c.lower() for c in sales_df.columns}
    joined = " ".join(suggestions).lower()
    assert any(col in joined for col in real_cols), (
        f"at least one suggestion should reference a real column {real_cols}: {suggestions}"
    )


@pytest.mark.usefixtures("_require_llm_key", "_data_dir")
def test_breakdown_returns_chart_spec_scalar_returns_null(api_client, sales_df):
    dataset_id = _upload(api_client, sales_df)
    session_id = _new_session(api_client, dataset_id)

    # A breakdown by category is chartable.
    breakdown = _ask(api_client, dataset_id, "Total sales by region?", session_id)
    assert breakdown["status"] == "completed", breakdown.get("error_message")
    spec = breakdown["chart_spec"]
    assert spec is not None, "expected a chart_spec for a categorical breakdown"
    assert spec["type"] == "bar"
    assert isinstance(spec["x"], list) and len(spec["x"]) >= 2
    assert spec["series"] and isinstance(spec["series"][0]["data"], list)

    # A single scalar answer is not chartable.
    scalar = _ask(api_client, dataset_id, "What is the grand total of sales?", session_id)
    assert scalar["status"] == "completed", scalar.get("error_message")
    assert scalar["chart_spec"] is None


@pytest.mark.usefixtures("_require_llm_key", "_data_dir")
def test_token_usage_accumulated_and_warn_is_bool(api_client, sales_df):
    dataset_id = _upload(api_client, sales_df)
    session_id = _new_session(api_client, dataset_id)

    body = _ask(api_client, dataset_id, "What is the total sales by region?", session_id)
    assert body["status"] == "completed", body.get("error_message")

    usage = body["token_usage"]
    assert usage["prompt"] > 0
    assert usage["completion"] > 0
    assert usage["total"] > 0
    assert isinstance(usage["warn"], bool)
    assert usage["warn"] is False  # a normal query is under the default threshold


@pytest.mark.usefixtures("_require_llm_key", "_data_dir")
def test_high_spend_trips_warn(api_client, sales_df, monkeypatch):
    # Force a tiny threshold so any real query trips the high-spend warning.
    monkeypatch.setenv("AGENT_TOKEN_WARN_THRESHOLD", "1")
    import config.settings as cfg
    cfg._settings = None  # rebuild settings with the low threshold

    dataset_id = _upload(api_client, sales_df)
    session_id = _new_session(api_client, dataset_id)

    body = _ask(api_client, dataset_id, "What is the total sales by region?", session_id)
    assert body["status"] == "completed", body.get("error_message")
    assert body["token_usage"]["total"] > 0
    assert body["token_usage"]["warn"] is True
