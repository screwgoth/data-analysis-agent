"""Phase-3 backend-multifile tests — join-key proposal + real cross-file analysis.

Real Gemini via .env, real subprocess sandbox, isolated SQLite DB (conftest).
Covers: deterministic join-key proposal, the HARD cross-file merge (answer key
number equals an in-test full-data pandas merge+groupby), privacy over BOTH
datasets, and a single-dataset regression.
"""
import json

import pandas as pd
import pytest

from analysis.join import propose_join_key


def _flatten(obj) -> str:
    return json.dumps(obj, default=str)


# --------------------------------------------------------------------------- #
# Deterministic join-key proposal (no LLM).
# --------------------------------------------------------------------------- #
def test_propose_join_key_returns_shared_compatible_column():
    orders = [
        {"name": "customer_id", "dtype": "int64"},
        {"name": "amount", "dtype": "float64"},
    ]
    customers = [
        {"name": "customer_id", "dtype": "Int32"},
        {"name": "region", "dtype": "object"},
    ]
    assert propose_join_key([orders, customers]) == "customer_id"


def test_propose_join_key_prefers_id_like_over_other_overlap():
    a = [
        {"name": "customer_id", "dtype": "int64"},
        {"name": "status", "dtype": "object"},
    ]
    b = [
        {"name": "customer_id", "dtype": "int64"},
        {"name": "status", "dtype": "object"},
    ]
    assert propose_join_key([a, b]) == "customer_id"


def test_propose_join_key_returns_none_when_no_overlap():
    a = [{"name": "order_id", "dtype": "int64"}]
    b = [{"name": "region", "dtype": "object"}]
    assert propose_join_key([a, b]) is None


def test_propose_join_key_none_when_shared_name_incompatible_dtype():
    a = [{"name": "id", "dtype": "int64"}]
    b = [{"name": "id", "dtype": "object"}]
    assert propose_join_key([a, b]) is None


def test_propose_join_key_none_for_single_dataset():
    assert propose_join_key([[{"name": "id", "dtype": "int64"}]]) is None


# --------------------------------------------------------------------------- #
# Fixtures + helpers for the real end-to-end path.
# --------------------------------------------------------------------------- #
@pytest.fixture
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path / "store"))
    yield


@pytest.fixture
def orders_df():
    # customer_id -> region mapping via customers_df:
    #   c1->North, c2->South, c3->North
    return pd.DataFrame(
        {
            "customer_id": ["c1", "c2", "c1", "c3", "c2", "c3"],
            "amount": [100, 200, 50, 300, 150, 400],
        }
    )


@pytest.fixture
def customers_df():
    return pd.DataFrame(
        {
            "customer_id": ["c1", "c2", "c3"],
            "region": ["North", "South", "North"],
            "name": ["Alice Green", "Bob Stone", "Carol White"],
        }
    )


def _upload(api_client, df, name):
    csv = df.to_csv(index=False).encode()
    r = api_client.post("/api/datasets", files={"file": (name, csv, "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


def _ask(api_client, dataset_ids, question, session_id=None):
    body = {"question": question, "dataset_ids": dataset_ids}
    if session_id:
        body["session_id"] = session_id
    r = api_client.post("/api/queries", json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"]


# --------------------------------------------------------------------------- #
# The HARD case: a question that REQUIRES joining two files.
# --------------------------------------------------------------------------- #
@pytest.mark.usefixtures("_require_llm_key", "_data_dir")
def test_cross_file_join_answer_matches_full_data(api_client, orders_df, customers_df):
    orders_id = _upload(api_client, orders_df, "orders.csv")
    customers_id = _upload(api_client, customers_df, "customers.csv")

    # A session that spans BOTH datasets.
    sess = api_client.post(
        "/api/sessions", json={"dataset_ids": [orders_id, customers_id]}
    )
    assert sess.status_code == 200, sess.text
    session_id = sess.json()["data"]["id"]

    body = _ask(
        api_client,
        [orders_id, customers_id],
        "What is the total amount by region? Join the orders to the customers on customer_id.",
        session_id,
    )
    assert body["status"] == "completed", body.get("error_message")

    # Ground truth computed in-test over the FULL data via the real merge.
    truth = (
        orders_df.merge(customers_df, on="customer_id")
        .groupby("region")["amount"]
        .sum()
        .to_dict()
    )
    assert truth == {"North": 850, "South": 350}

    steps_blob = _flatten([s.get("result_json") for s in body["steps"]])
    answer = body["answer"] or ""
    for region, total in truth.items():
        assert (
            str(total) in steps_blob or str(total) in answer
        ), f"expected {region} total={total} in cross-file result/answer"

    # A real merge/join must appear in the generated, executed code.
    code_blob = " ".join(s.get("code", "") for s in body["steps"]).lower()
    assert "merge" in code_blob or "join" in code_blob, (
        f"expected a real merge/join in the generated code, got:\n{code_blob}"
    )

    # Standard response envelope is present.
    assert "suggestions" in body
    assert "chart_spec" in body
    assert body["token_usage"]["total"] > 0


# --------------------------------------------------------------------------- #
# Privacy: only masked samples + schema for BOTH datasets reach the LLM.
# --------------------------------------------------------------------------- #
@pytest.mark.usefixtures("_require_llm_key", "_data_dir")
def test_no_raw_rows_from_either_dataset_reach_llm(
    api_client, orders_df, customers_df, monkeypatch
):
    captured = {"prompts": []}

    from llm.client import LLMClient

    original = LLMClient.call_model_with_usage

    def _spy(self, prompt, *args, **kwargs):
        captured["prompts"].append(prompt)
        captured["prompts"].append(kwargs.get("system", ""))
        return original(self, prompt, *args, **kwargs)

    monkeypatch.setattr(LLMClient, "call_model_with_usage", _spy)

    orders_id = _upload(api_client, orders_df, "orders.csv")
    customers_id = _upload(api_client, customers_df, "customers.csv")

    body = _ask(
        api_client,
        [orders_id, customers_id],
        "Total amount by region across the two files.",
    )
    assert body["status"] == "completed", body.get("error_message")

    all_prompts = "\n".join(captured["prompts"])
    # Raw PII names from customers_df must never appear unmasked in any prompt.
    for raw in ["Alice Green", "Bob Stone", "Carol White"]:
        assert raw not in all_prompts, f"raw PII value leaked to LLM: {raw}"


# --------------------------------------------------------------------------- #
# Single-dataset regression: still works exactly as before.
# --------------------------------------------------------------------------- #
@pytest.mark.usefixtures("_require_llm_key", "_data_dir")
def test_single_dataset_still_works(api_client, orders_df):
    orders_id = _upload(api_client, orders_df, "orders.csv")

    body = _ask(api_client, [orders_id], "What is the total amount?")
    assert body["status"] == "completed", body.get("error_message")

    truth = int(orders_df["amount"].sum())
    assert truth == 1200
    blob = _flatten([s.get("result_json") for s in body["steps"]]) + (body["answer"] or "")
    assert str(truth) in blob, f"expected total amount {truth} in single-dataset answer"
