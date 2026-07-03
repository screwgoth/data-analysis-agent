# Data Model

---

## Storage Technology

SQLite + SQLAlchemy 2.0 (Alembic migrations). SQLite is the production database for this deliberately local, single-user app. Uploaded raw files live on the local filesystem under `data/datasets/<dataset_id>/`; only metadata, profiles, masked samples, sessions, queries, and the audit trail live in SQLite.

## Entities

### Entity: Dataset
An uploaded tabular file in the persistent library.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| name | str | yes | Display name (defaults to filename) |
| filename | str | yes | Original uploaded file name |
| source_format | str | yes | csv \| xlsx \| pdf |
| local_path | str | yes | Canonical local CSV path the executor reads |
| row_count | int | yes | Rows |
| col_count | int | yes | Columns |
| masked_sample | JSON (text) | yes | ≤5 PII-masked rows — the only rows allowed to reach the LLM |
| created_at | timestamp | yes | Ingest time |
| updated_at | timestamp | yes | Last change |

### Entity: DatasetProfile
Auto-computed profile, one per dataset.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| dataset_id | str (FK) | yes | → Dataset.id |
| columns | JSON (text) | yes | Per column: name, dtype, missing_count, distinct_count, min/max/mean, likely_pii |
| created_at | timestamp | yes | |

### Entity: Session
A long-lived conversation over one or more datasets (Phase 2).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| dataset_ids | JSON (text) | yes | Active datasets for the session |
| created_at | timestamp | yes | |
| updated_at | timestamp | yes | |

### Entity: Query
One natural-language question and its answer.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key (also the graph run_id) |
| session_id | str (FK) | no | → Session.id (Phase 2; null in Phase 1) |
| dataset_ids | JSON (text) | no | Active dataset id(s) for this query (multi-file support) |
| question | str | yes | User question |
| plan | str | no | Agent strategy |
| answer | str | no | Prose + key numbers |
| assumptions | JSON (text) | no | Flagged assumptions |
| clarifying_question | str | no | Set when the agent asked instead of answering |
| chart_spec | JSON (text) | no | Chart spec (Phase 2) |
| suggestions | JSON (text) | no | 2–3 follow-ups (Phase 2) |
| token_usage | JSON (text) | no | {prompt, completion, total} |
| status | str | yes | pending \| completed \| failed |
| error_message | str | no | On failure |
| created_at | timestamp | yes | |

### Entity: AnalysisStep
The audit trail — one row per executed code step.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| query_id | str (FK) | yes | → Query.id |
| step_index | int | yes | Order within the query |
| code | str | yes | Exact code executed |
| stdout | str | no | Captured stdout |
| result_json | JSON (text) | no | Captured result (records/repr) |
| error | str | no | Error/traceback if the step failed |
| duration_ms | int | yes | Execution time |
| created_at | timestamp | yes | |

### Relationships

- Dataset 1—1 DatasetProfile.
- Session 1—* Query; Query 1—* AnalysisStep.
- Session *—* Dataset via `Session.dataset_ids`.
- (The boilerplate `runs` table is superseded by `Query` + `AnalysisStep`.)

## Data Lifecycle

- Dataset + Profile + masked_sample created on upload; persist across days until the user deletes them (Phase 3 delete removes the row and the local file).
- Query + AnalysisStep created per question; retained as the audit trail (not auto-purged).
- Sessions persist; history is read from a session's Query rows.

## Sensitive Data

- Raw data files contain the user's real (possibly sensitive) data; they never leave the machine.
- `Dataset.masked_sample` and any LLM-bound context have PII columns masked (`masking.py`). Likely-PII columns are flagged in the profile.
- No secrets stored in the DB; the Gemini key lives in `.env` (gitignored) and is confirmed by presence only.
