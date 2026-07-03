"""Export a query's result as CSV/XLSX (seeded Query+AnalysisStep — no LLM)."""
import io

import pandas as pd

from analysis.export import build_export, result_to_dataframe


def _seed_query(engine) -> str:
    from sqlalchemy.orm import sessionmaker
    from db.models import Query, AnalysisStep

    Factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Factory() as s:
        q = Query(question="revenue by region?", dataset_ids=["x"], status="completed",
                  answer="North leads.")
        s.add(q)
        s.flush()
        qid = q.id
        s.add(AnalysisStep(query_id=qid, step_index=0, code="RESULT=df.head()",
                           result_json=[{"region": "North", "revenue": 100},
                                        {"region": "South", "revenue": 250}]))
        s.commit()
    return qid


def test_result_to_dataframe_variants():
    assert list(result_to_dataframe([{"a": 1}, {"a": 2}]).columns) == ["a"]
    assert list(result_to_dataframe({"North": 100, "South": 250}).columns) == ["key", "value"]
    assert result_to_dataframe(42)["value"].iloc[0] == 42


def test_build_export_csv_roundtrip():
    data, media, ext = build_export([{"region": "North", "revenue": 100}], "csv")
    assert media == "text/csv" and ext == "csv"
    df = pd.read_csv(io.BytesIO(data))
    assert df["region"].iloc[0] == "North"


def test_build_export_bad_format():
    import pytest

    with pytest.raises(ValueError):
        build_export([{"a": 1}], "json")


def test_export_csv_endpoint(api_client, _isolated_db):
    qid = _seed_query(_isolated_db)
    resp = api_client.get(f"/api/queries/{qid}/export", params={"format": "csv"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    df = pd.read_csv(io.BytesIO(resp.content))
    assert set(df["region"]) == {"North", "South"}
    assert list(df["revenue"]) == [100, 250]


def test_export_xlsx_endpoint(api_client, _isolated_db):
    qid = _seed_query(_isolated_db)
    resp = api_client.get(f"/api/queries/{qid}/export", params={"format": "xlsx"})
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    df = pd.read_excel(io.BytesIO(resp.content), engine="openpyxl")
    assert list(df["revenue"]) == [100, 250]


def test_export_unknown_query_404(api_client):
    resp = api_client.get("/api/queries/nope/export", params={"format": "csv"})
    assert resp.status_code == 404


def test_export_bad_format_400(api_client, _isolated_db):
    qid = _seed_query(_isolated_db)
    resp = api_client.get(f"/api/queries/{qid}/export", params={"format": "json"})
    assert resp.status_code == 400
