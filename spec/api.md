# API

---

## API Style

REST/JSON over HTTP, same-origin, served by FastAPI under `/api`. All responses use the boilerplate envelope (`ok(...)` / error envelope). The Next.js static export is served at `/app`.

## Endpoints / Commands

### `POST /api/datasets` (Phase 1: CSV; Phase 3: xlsx/pdf)
**Purpose:** Upload a file; store locally, profile it, compute masked sample.
**Request:** `multipart/form-data` — `file` (binary), optional `name`.
**Response:**
```json
{ "id": "uuid", "name": "sales.csv", "row_count": 1200, "col_count": 8,
  "profile": { "columns": [ { "name": "region", "dtype": "string", "missing_count": 0, "likely_pii": false } ] } }
```
| Status | Condition |
|--------|-----------|
| 400 | unparseable file |
| 413 | file over ~100MB |
| 500 | storage/profiling failure |

### `GET /api/datasets` / `GET /api/datasets/{id}` (Phase 3 for list UI)
**Purpose:** List library datasets / fetch one with its profile.

### `PATCH /api/datasets/{id}` / `DELETE /api/datasets/{id}` (Phase 3)
**Purpose:** Rename / delete a dataset (delete also removes the local file).

### `POST /api/queries`
**Purpose:** Ask a question; runs the agent graph synchronously and returns the answer.
**Request:**
```json
{ "question": "total revenue by region?", "dataset_ids": ["uuid"], "session_id": "uuid|null" }
```
**Response:**
```json
{ "id": "uuid", "status": "completed",
  "answer": "Total revenue... North: 1.2M...",
  "assumptions": [], "clarifying_question": null,
  "steps": [ { "step_index": 0, "code": "RESULT = df.groupby('region')...", "stdout": "", "result_json": {}, "error": null, "duration_ms": 42 } ],
  "chart_spec": null, "suggestions": [], "token_usage": { "prompt": 900, "completion": 300, "total": 1200, "warn": false } }
```
| Status | Condition |
|--------|-----------|
| 400 | missing question / unknown dataset_id |
| 500 | agent infra failure (status="failed", error_message surfaced) |

`chart_spec`, `suggestions`, `token_usage.warn` populate in Phase 2; `clarifying_question` in Phase 2.

### `POST /api/sessions` / `GET /api/sessions/{id}` (Phase 2)
**Purpose:** Create a session over dataset(s); fetch its history (ordered Query rows).

### `GET /api/queries/{id}/export?format=csv|xlsx` (Phase 3)
**Purpose:** Download the query's result/cleaned data as a file.
| Status | Condition |
|--------|-----------|
| 400 | invalid/unknown `format` value (must be csv or xlsx) |
| 404 | unknown query |
| 500 | export build failure |

## Authentication

None — single-user local app bound to localhost. No auth layer by design (documented out-of-scope).
