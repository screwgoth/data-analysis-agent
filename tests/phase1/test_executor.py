"""Subprocess code-execution sandbox tests (no LLM key required)."""
import pandas as pd

from analysis.executor import execute_code


def _write_csv(tmp_path) -> str:
    df = pd.DataFrame({"region": ["N", "S", "N"], "revenue": [10, 20, 30]})
    path = tmp_path / "d.csv"
    df.to_csv(path, index=False)
    return str(path)


def test_executor_runs_pandas_and_captures_result(tmp_path):
    path = _write_csv(tmp_path)
    code = "RESULT = df.groupby('region')['revenue'].sum().to_dict()"
    out = execute_code(code, [path], timeout=30)
    assert out["error"] is None
    assert out["result_json"] == {"N": 40, "S": 20}
    assert out["duration_ms"] >= 0


def test_executor_captures_stdout(tmp_path):
    path = _write_csv(tmp_path)
    code = "print('hello from sandbox')\nRESULT = int(df['revenue'].sum())"
    out = execute_code(code, [path], timeout=30)
    assert out["error"] is None
    assert out["result_json"] == 60
    assert "hello from sandbox" in out["stdout"]


def test_executor_broken_code_captured_not_crashed(tmp_path):
    path = _write_csv(tmp_path)
    code = "RESULT = df['does_not_exist'].sum()"
    out = execute_code(code, [path], timeout=30)
    assert out["error"] is not None
    assert "KeyError" in out["error"] or "does_not_exist" in out["error"]
    assert out["result_json"] is None


def test_executor_dataframe_result_serialized(tmp_path):
    path = _write_csv(tmp_path)
    code = "RESULT = df.groupby('region', as_index=False)['revenue'].sum()"
    out = execute_code(code, [path], timeout=30)
    assert out["error"] is None
    assert isinstance(out["result_json"], list)
    assert {"region": "N", "revenue": 40} in out["result_json"]
