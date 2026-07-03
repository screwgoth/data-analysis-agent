# Capability: Iterative Code Analysis

## What It Does
Answers a natural-language question about a dataset by planning a strategy, writing pandas code, executing it LOCALLY against the real data, inspecting results and iterating (bounded step limit), then returning a prose answer with key numbers plus the exact code it ran.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | string | user | yes |
| dataset_id(s) | string / list | active session | yes |
| schema_context | JSON | `DatasetProfile` | yes |
| masked_sample | JSON | `Dataset.masked_sample` | yes |
| history | list of turns | session (Phase 2+) | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer | prose + key numbers | UI, `Query.answer` |
| shown_code | list of executed steps (code + stdout/result) | UI (collapsible), `AnalysisStep` rows |
| assumptions | list of flagged assumptions when the question is ambiguous | UI |
| token_usage | prompt/completion token counts (displayed Phase 2+) | `Query.token_usage` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | plan / write-code / reflect / answer | retry once, then set error and finalize with a surfaced message |
| Local Python subprocess | execute generated pandas code against the real file | captured as a failed step; agent reflects and retries code (bounded), not fatal |

## Business Rules
- The LLM receives ONLY schema + PII-masked sample rows — never raw data rows.
- Code executes locally in an isolated subprocess with a wall-clock timeout and no network access.
- Iteration is bounded (`max_steps`, default 6); on exhaustion the agent answers with best-available results and flags the limit.
- Every executed step persists the exact code and its captured stdout/result/error (audit trail) before the next step runs.
- On ambiguity, the agent either asks a clarifying question (Phase 2+) or gives a best guess clearly flagged with assumptions.

## Success Criteria
- [ ] Asking a quantitative question over a real CSV returns a prose answer whose key number equals the value computed by running pandas over the FULL dataset (not a sample).
- [ ] The response includes the exact code executed and its captured output for every step.
- [ ] A deliberately hard question that fails on the first code attempt shows ≥2 `AnalysisStep` rows (a failed attempt then a corrected one).
- [ ] The LLM request payload contains schema + masked sample only — asserted to contain no raw non-masked PII value.
- [ ] Step count never exceeds `max_steps`.
