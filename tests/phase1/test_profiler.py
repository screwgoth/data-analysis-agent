"""Profiler + masking unit tests (no LLM key required)."""
import pandas as pd

from analysis.masking import build_masked_sample, likely_pii, mask_value
from analysis.profiler import profile_csv, profile_dataframe


def _sales_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "region": ["North", "South", "North", "West", None],
            "revenue": [100.0, 250.5, 75.0, 300.0, 50.0],
            "units": [1, 3, 2, 4, 1],
            "email": [
                "alice@example.com",
                "bob@example.com",
                "carol@example.com",
                "dan@example.com",
                "eve@example.com",
            ],
        }
    )


def test_profile_columns_types_and_missing():
    profile = profile_dataframe(_sales_df())
    cols = {c["name"]: c for c in profile["columns"]}

    assert cols["region"]["dtype"] == "string"
    assert cols["region"]["missing_count"] == 1
    assert cols["revenue"]["dtype"] == "float"
    assert cols["units"]["dtype"] == "integer"


def test_profile_numeric_ranges():
    profile = profile_dataframe(_sales_df())
    revenue = next(c for c in profile["columns"] if c["name"] == "revenue")
    assert revenue["min"] == 50.0
    assert revenue["max"] == 300.0
    assert revenue["range"] == 250.0


def test_email_column_flagged_pii_and_masked():
    df = _sales_df()
    profile = profile_dataframe(df)
    email_col = next(c for c in profile["columns"] if c["name"] == "email")
    assert email_col["likely_pii"] is True

    sample = profile["masked_sample"]
    # No raw email value may appear in the masked sample.
    for row in sample:
        assert "alice@example.com" not in str(row.values())
        assert "@example.com" in str(row["email"])  # domain kept, local masked


def test_masking_helpers():
    assert likely_pii("customer_email", pd.Series(["a@b.com"])) is True
    assert likely_pii("region", pd.Series(["North", "South"])) is False
    masked = mask_value("alice@example.com")
    assert "alice" not in masked
    assert masked.startswith("a")


def test_profile_csv_roundtrip(tmp_path):
    path = tmp_path / "s.csv"
    _sales_df().to_csv(path, index=False)
    result = profile_csv(path)
    assert result["row_count"] == 5
    assert result["col_count"] == 4
    assert len(result["masked_sample"]) == 5


def test_build_masked_sample_masks_only_pii():
    df = _sales_df()
    sample = build_masked_sample(df, pii_columns=["email"], n=2)
    assert len(sample) == 2
    # Non-PII values preserved.
    assert sample[0]["region"] == "North"
    assert sample[0]["revenue"] == 100.0
