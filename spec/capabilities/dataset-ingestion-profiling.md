# Capability: Dataset Ingestion & Profiling

## What It Does
Ingests a tabular file into the local dataset library and auto-profiles it (columns, types, ranges, missing values) so the user and the agent both know the shape of the data before any question is asked.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | binary (CSV in Phase 1; Excel/PDF-table in Phase 3) | user upload | yes |
| display_name | string | user (defaults to filename) | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset record | `Dataset` row (id, name, path, row/col counts, created_at) | SQLite + local file store |
| profile | `DatasetProfile` JSON (per-column type, min/max/mean, distinct count, missing count, likely-PII flag) | SQLite, shown in UI |
| masked_sample | JSON (≤5 rows, PII columns masked) | SQLite, used only when talking to the LLM |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Local filesystem | write uploaded file to `data/datasets/<id>/` | fatal — return 400/500, no dataset row committed |
| pandas | read file, compute profile | fatal — surface "could not parse file" with reason |

## Business Rules
- Files up to ~100MB accepted; larger → 413 with a clear message.
- Profiling runs locally only; raw rows never leave the machine.
- A column is flagged likely-PII by name+value heuristics (email/phone/name/SSN-like patterns); flagged columns are masked in `masked_sample`.
- Phase 1 supports CSV only; Excel (.xlsx) and PDF-extracted tables are added in Phase 3.

## Success Criteria
- [ ] Uploading a real CSV creates a `Dataset` row and stores the file under `data/datasets/<id>/`.
- [ ] The returned profile lists every column with its inferred type, missing-value count, and numeric range where applicable.
- [ ] Any column whose values match the PII heuristics is masked in `masked_sample` (asserted on a fixture containing an email column).
- [ ] A file over the size limit is rejected with a 413 and no partial dataset row.
