import sys
from pathlib import Path

import uvicorn

# Ensure the package modules (api, graph, db, ...) are importable when launched
# as `python -m src` from the repo root.
_SRC = str(Path(__file__).resolve().parent)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=False)
