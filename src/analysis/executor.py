"""Local subprocess code-execution sandbox — the privacy boundary.

Generated pandas code is run in a *fresh* Python subprocess (Windows-safe:
``subprocess.run`` with ``sys.executable`` — never ``os.exec*``) against the REAL
local dataset file(s). Raw data is read ONLY here; it never reaches the LLM.
Everything is captured: the ``RESULT`` variable (JSON-serialized), stdout, any
error/traceback, and the wall-clock duration. A crash or timeout is captured as a
failed step, not a server crash.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Runner harness executed inside the subprocess. Reads an input JSON file
# (argv[1]) with {"code": str, "paths": [str, ...]} and prints a single JSON
# envelope on stdout delimited by a sentinel so we can separate it from any
# stdout the user code produced.
_SENTINEL = "<<<EXECUTOR_RESULT_JSON>>>"

_HARNESS = r'''
import json, sys, io, contextlib, traceback

SENTINEL = "__SENTINEL_TOKEN__"

def _to_jsonable(obj):
    try:
        import pandas as pd
    except Exception:
        pd = None
    if pd is not None:
        if isinstance(obj, pd.DataFrame):
            return obj.head(200).to_dict(orient="records")
        if isinstance(obj, pd.Series):
            return obj.head(200).to_dict()
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            pass
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)

def main():
    with open(sys.argv[1], "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    code = payload["code"]
    paths = payload["paths"]

    import pandas as pd

    ns = {"pd": pd}
    error = None
    tb = None
    try:
        frames = [pd.read_csv(p) for p in paths]
        if frames:
            ns["df"] = frames[0]
        for i, frame in enumerate(frames, start=1):
            ns["df%d" % i] = frame
    except Exception:
        error = "Failed to load dataset(s)"
        tb = traceback.format_exc()
        print(SENTINEL + json.dumps({"stdout": "", "result_json": None,
              "error": error + "\n" + tb}))
        return

    buf = io.StringIO()
    result = None
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, ns)
        result = ns.get("RESULT")
    except Exception:
        error = "".join(traceback.format_exc())

    out = {
        "stdout": buf.getvalue(),
        "result_json": _to_jsonable(result) if error is None else None,
        "error": error,
    }
    print(SENTINEL + json.dumps(out))

main()
'''.replace("__SENTINEL_TOKEN__", _SENTINEL)


def execute_code(code: str, dataset_paths: list[str], timeout: int = 30) -> dict:
    """Run generated pandas code against real local file(s) in a subprocess.

    Returns ``{stdout, result_json, error, duration_ms}``. Never raises for user
    code errors or timeouts — those come back as ``error``.
    """
    start = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        harness_file = tmp_path / "harness.py"
        input_file = tmp_path / "input.json"
        harness_file.write_text(_HARNESS, encoding="utf-8")
        input_file.write_text(
            json.dumps({"code": code, "paths": [str(p) for p in dataset_paths]}),
            encoding="utf-8",
        )

        try:
            proc = subprocess.run(
                [sys.executable, str(harness_file), str(input_file)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return {
                "stdout": "",
                "result_json": None,
                "error": f"Execution timed out after {timeout}s",
                "duration_ms": duration_ms,
            }
        except OSError as exc:  # spawn failure — Windows-safe degradation
            duration_ms = int((time.perf_counter() - start) * 1000)
            return {
                "stdout": "",
                "result_json": None,
                "error": f"Failed to launch execution subprocess: {exc}",
                "duration_ms": duration_ms,
            }

    duration_ms = int((time.perf_counter() - start) * 1000)
    raw = proc.stdout or ""
    if _SENTINEL in raw:
        pre, _, payload = raw.rpartition(_SENTINEL)
        try:
            envelope = json.loads(payload.strip())
        except json.JSONDecodeError:
            return {
                "stdout": raw,
                "result_json": None,
                "error": "Could not parse execution envelope",
                "duration_ms": duration_ms,
            }
        # stdout printed before the sentinel is the user code's own stdout,
        # but the harness already captured it via redirect; prefer envelope.
        return {
            "stdout": envelope.get("stdout", ""),
            "result_json": envelope.get("result_json"),
            "error": envelope.get("error"),
            "duration_ms": duration_ms,
        }

    # No sentinel → the harness itself failed (syntax/interpreter). Capture stderr.
    return {
        "stdout": raw,
        "result_json": None,
        "error": (proc.stderr or "Execution produced no result").strip(),
        "duration_ms": duration_ms,
    }
