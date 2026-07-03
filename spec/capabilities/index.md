# Capabilities Index

> One file per capability. Each describes exactly one discrete thing the agent can do.

---

## Capabilities in This Project

| Capability | File | First delivered |
|-----------|------|-----------------|
| Dataset Ingestion & Profiling | [dataset-ingestion-profiling.md](dataset-ingestion-profiling.md) | Phase 1 (CSV) → Phase 3 (Excel/PDF) |
| Iterative Code Analysis | [iterative-analysis.md](iterative-analysis.md) | Phase 1 |
| Conversational Analysis Session | [conversational-session.md](conversational-session.md) | Phase 2 |
| Visualization, Library & Export | [visualization-export.md](visualization-export.md) | Phase 2 (charts/tables/tokens) → Phase 3 (library/multi-file/export) |

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer sub-agent creates a new `<name>.md`, updates this index, flags dependencies, and self-reviews fit before returning.
