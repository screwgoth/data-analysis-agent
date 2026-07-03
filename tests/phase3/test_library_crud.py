"""Persistent library CRUD: list / fetch-one / rename / delete (no LLM)."""
from pathlib import Path


def _make_csv() -> bytes:
    return b"region,revenue\nNorth,100\nSouth,250\n"


def _upload(api_client, name: str) -> dict:
    files = {"file": (f"{name}.csv", _make_csv(), "text/csv")}
    resp = api_client.post("/api/datasets", files=files, data={"name": name})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_list_returns_all_datasets(api_client):
    a = _upload(api_client, "alpha")
    b = _upload(api_client, "beta")
    resp = api_client.get("/api/datasets")
    assert resp.status_code == 200
    rows = resp.json()["data"]
    ids = {r["id"] for r in rows}
    assert {a["id"], b["id"]} <= ids
    row = next(r for r in rows if r["id"] == a["id"])
    assert row["source_format"] == "csv"
    assert row["row_count"] == 2
    assert "created_at" in row


def test_get_one_returns_profile(api_client):
    a = _upload(api_client, "alpha")
    resp = api_client.get(f"/api/datasets/{a['id']}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == a["id"]
    col_names = {c["name"] for c in data["profile"]["columns"]}
    assert col_names == {"region", "revenue"}


def test_get_unknown_404(api_client):
    resp = api_client.get("/api/datasets/does-not-exist")
    assert resp.status_code == 404


def test_patch_renames_persisted(api_client):
    a = _upload(api_client, "alpha")
    resp = api_client.patch(f"/api/datasets/{a['id']}", json={"name": "renamed"})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "renamed"
    # Persisted across a fresh read.
    again = api_client.get(f"/api/datasets/{a['id']}")
    assert again.json()["data"]["name"] == "renamed"


def test_patch_empty_name_400(api_client):
    a = _upload(api_client, "alpha")
    resp = api_client.patch(f"/api/datasets/{a['id']}", json={"name": "   "})
    assert resp.status_code == 400


def test_delete_removes_row_and_local_file(api_client):
    a = _upload(api_client, "alpha")
    detail = api_client.get(f"/api/datasets/{a['id']}")
    assert detail.status_code == 200

    # Find the on-disk file before delete.
    from config.settings import get_settings

    ds_dir = Path(get_settings().data_dir) / "datasets" / a["id"]
    assert ds_dir.exists()

    resp = api_client.delete(f"/api/datasets/{a['id']}")
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] is True

    assert api_client.get(f"/api/datasets/{a['id']}").status_code == 404
    assert not ds_dir.exists()


def test_delete_unknown_404(api_client):
    resp = api_client.delete("/api/datasets/nope")
    assert resp.status_code == 404
