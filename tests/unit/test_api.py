"""API contract tests — no LLM key required, graph is not invoked."""


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


def test_query_missing_question(api_client):
    r = api_client.post("/api/queries", json={"question": "", "dataset_ids": ["x"]})
    assert r.status_code == 400


def test_query_unknown_dataset(api_client):
    r = api_client.post(
        "/api/queries", json={"question": "total?", "dataset_ids": ["does-not-exist"]}
    )
    assert r.status_code == 400


def test_dataset_rejects_non_csv(api_client):
    r = api_client.post(
        "/api/datasets",
        files={"file": ("data.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400
