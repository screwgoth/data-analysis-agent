# Capability: Conversational Analysis Session

## What It Does
Maintains a long-lived, multi-turn session so follow-up questions like "and by region?" resolve against prior turns, and proactively suggests 2–3 relevant follow-up questions after each answer. (Phase 2)

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | string | user | yes |
| session_id | string | active session | yes |
| prior turns | list of {question, answer, steps} | `Query` rows for the session | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| resolved question context | prompt context | agent `plan` node |
| answer | prose + numbers | UI, `Query.answer` |
| suggestions | 2–3 follow-up questions | UI (clickable), `Query.suggestions` |
| clarifying_question | string (when ambiguous) | UI |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | resolve follow-up against history; generate suggestions; decide clarify-vs-guess | degrade: answer without suggestions rather than fail |

## Business Rules
- Conversation history is scoped to a session and passed to the `plan` node so pronouns/ellipsis resolve to prior turns.
- Suggestions must be answerable from the loaded dataset(s), not generic.
- When a question is ambiguous AND a clarification would materially change the answer, ask one clarifying question instead of guessing; otherwise guess and flag the assumption.
- History is truncated/summarized to stay within the context window (most recent N turns kept verbatim).

## Success Criteria
- [ ] After asking "average sales by month?", asking "and just for 2024?" returns an answer scoped to 2024 without the user restating "sales by month".
- [ ] Each answer is followed by 2–3 follow-up suggestions that reference real columns of the loaded dataset.
- [ ] An intentionally ambiguous question ("show me the top ones") triggers a clarifying question, asserted in the response.
- [ ] Session history persists across page reload (reloading and asking a follow-up still resolves).
