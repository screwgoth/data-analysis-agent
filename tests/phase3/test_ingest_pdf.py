"""PDF table ingestion — generate a ruled table PDF via reportlab, upload it.

PDF table extraction is best-effort; these tests assert (a) a well-ruled table
extracts + profiles correctly, and (b) a PDF with no table degrades gracefully
to a 400 rather than a 500 crash.
"""
import io

import pytest

from analysis.ingest import load_pdf


def _table_pdf_bytes() -> bytes:
    reportlab = pytest.importorskip("reportlab")  # noqa: F841
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    data = [
        ["region", "revenue", "units"],
        ["North", "100", "1"],
        ["South", "250", "3"],
        ["West", "300", "4"],
    ]
    table = Table(data)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )
    doc.build([table])
    return buf.getvalue()


def _blank_pdf_bytes() -> bytes:
    pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    doc.build([Paragraph("Just some prose, no table here.", getSampleStyleSheet()["Normal"])])
    return buf.getvalue()


def test_load_pdf_extracts_table():
    df = load_pdf(_table_pdf_bytes())
    assert list(df.columns) == ["region", "revenue", "units"]
    assert len(df) == 3
    assert set(df["region"]) == {"North", "South", "West"}


def test_load_pdf_no_table_raises_valueerror():
    with pytest.raises(ValueError):
        load_pdf(_blank_pdf_bytes())


def test_load_pdf_corrupt_bytes_raises_not_crash():
    with pytest.raises(ValueError):
        load_pdf(b"%PDF-corrupt-not-really")


def test_upload_pdf_profiles(api_client):
    files = {"file": ("report.pdf", _table_pdf_bytes(), "application/pdf")}
    resp = api_client.post("/api/datasets", files=files)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["row_count"] == 3
    assert data["col_count"] == 3


def test_upload_pdf_no_table_returns_400_not_500(api_client):
    files = {"file": ("prose.pdf", _blank_pdf_bytes(), "application/pdf")}
    resp = api_client.post("/api/datasets", files=files)
    assert resp.status_code == 400, resp.text
