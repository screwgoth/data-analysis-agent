"""File-format ingestion for the dataset library (Phase 3).

Each loader turns raw uploaded bytes into a pandas ``DataFrame``. The upload
endpoint then profiles the frame and stores a canonical local CSV so the
subprocess executor keeps reading local data only. Loaders raise ``ValueError``
on unparseable input; the endpoint maps that to a 400.
"""
from __future__ import annotations

from analysis.ingest.excel import load_excel
from analysis.ingest.pdf import load_pdf

__all__ = ["load_excel", "load_pdf"]
