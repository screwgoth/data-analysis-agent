# Capability: Visualization, Library & Export

## What It Does
Turns answers into interactive charts and summary tables, manages the persistent multi-day dataset library (including Excel/PDF ingestion and multi-file join/compare), and exports cleaned data or results. Shows per-query token counts with a high-spend warning. (Phases 2–3)

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| analysis result | DataFrame/records | `AnalysisStep` result | yes |
| chart intent | spec (type, x, y, series) | agent `answer` node | no |
| export request | {query_id or dataset_id, format} | user | no |
| library actions | select / rename / delete / join datasets | user | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| chart spec | JSON (chart type, data, axes) | UI (interactive chart) |
| summary table | records | UI (sortable table) |
| export file | CSV / XLSX | download |
| token badge | {prompt, completion, total, warn:bool} | UI |
| library view | list of datasets with profiles | UI |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Local Python subprocess | build chart data / cleaned export from real data | surface error; no partial file download |
| pandas + openpyxl / pdf table extractor | ingest Excel / PDF tables (Phase 3) | mark ingestion failed with reason; dataset not created |

## Business Rules
- Charts are generated from locally-computed result data only; raw data is not sent to the LLM to render a chart.
- Multi-file join/compare requires the user to pick a join key; the agent proposes one from overlapping columns.
- Export produces the exact cleaned/result data the user sees, from local computation.
- Token counts are shown per query; a query exceeding the configurable threshold shows a warning badge. Dollar cost is never shown.
- The library persists across days (SQLite-backed); datasets remain loaded until deleted.

## Success Criteria
- [ ] An answer that trends a numeric column over a category renders an interactive chart the user can hover/explore.
- [ ] Uploading a real .xlsx and a PDF containing a table each create profiled `Dataset` rows.
- [ ] Joining two datasets on a shared key answers a cross-file question with the correct joined result.
- [ ] Exporting a result downloads a file whose contents match the on-screen table exactly.
- [ ] A query above the token threshold shows the high-spend warning badge; a normal query does not.
