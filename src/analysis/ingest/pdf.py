"""PDF table ingestion (best-effort).

Uses pdfplumber to extract tables from a PDF and returns the LARGEST table
found (by cell count) as a DataFrame, treating its first row as the header.

PDF table extraction is inherently best-effort — a PDF is a layout format, not
a data format. We handle the common case of a ruled/well-aligned table. If no
table can be found we raise ``ValueError`` (mapped to a 400 by the endpoint) so
the failure is graceful and never a 500 crash.
"""
from __future__ import annotations

import io

import pandas as pd
import pdfplumber


def _table_to_frame(table: list[list]) -> pd.DataFrame | None:
    if not table or len(table) < 2:
        return None
    header = [str(c).strip() if c is not None else f"col_{i}" for i, c in enumerate(table[0])]
    # De-duplicate / fill blank headers so pandas gets unique column names.
    seen: dict[str, int] = {}
    cols: list[str] = []
    for i, h in enumerate(header):
        name = h or f"col_{i}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        cols.append(name)
    rows = [r for r in table[1:] if any(c is not None and str(c).strip() != "" for c in r)]
    if not rows:
        return None
    return pd.DataFrame(rows, columns=cols)


def load_pdf(file_bytes: bytes) -> pd.DataFrame:
    """Extract the largest table from a PDF into a DataFrame.

    Raises ``ValueError`` if the PDF cannot be opened or contains no table.
    """
    best: pd.DataFrame | None = None
    best_cells = 0
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    frame = _table_to_frame(table)
                    if frame is None:
                        continue
                    cells = frame.shape[0] * frame.shape[1]
                    if cells > best_cells:
                        best, best_cells = frame, cells
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 — corrupt/unopenable PDF → clean 400
        raise ValueError(f"Could not read PDF file: {exc}") from exc

    if best is None:
        raise ValueError(
            "No extractable table found in PDF. PDF table extraction is "
            "best-effort and needs a ruled or well-aligned table."
        )
    return best
