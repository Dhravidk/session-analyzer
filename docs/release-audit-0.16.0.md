# 0.16.0 — session questions without the GUI

The plugin now supports focused Claude Code conversations over the same captured session evidence as the report. This release changes tooling and guidance; it does not rewrite earlier Claude output or claim that model judgments are reliably correct.

## Implemented

- Expanded the existing automatically discoverable `explain` skill rather than adding a competing chat skill. It covers explicit scope selection, task/turn/resource questions, primary-evidence checks, historical instruction attribution, and corrections to unsupported previous answers.
- `get_session_guide` returns the exact bundled instructions and hash. Definitions or the first successful data call deliver both conversation and writing skills once per connection, including when the native Skill tool is unavailable. Oversized responses do not mark rejected guide delivery as successful. Delivery is not proof that Claude followed the instructions.
- `list_session_investigations` discovers saved metadata within the selected analysis/session, including partial runs. A bound connection cannot use it to switch scope. It does not infer freshness or live execution from a saved status.
- `query_measurement` reuses the registered calculation engine on active or finalized investigations. Queries include population identities, coverage, versions and unknown states. They append access receipts and may populate deterministic caches; they do not change saved runs, measurements, findings or conclusions.
- Exclusive `agent_id` selection with `turn_id` or `all_scoped` separates main/child usage without loading hundreds of IDs into the prompt. Shared identities are excluded and disclosed. Missing child traces are unavailable rather than zero. Unfiltered turn metrics can include linked children.
- `inspect_response_accounting` exposes paged captured numeric fields alongside reconciled usage, frame indices, missing/invalid states, warnings, hashes and line references. No message or thinking text is exposed through this metadata API. Captured telemetry is not independent provider verification.
- Added CLI discovery/guide commands, a repeatable opt-in three-question Claude exercise, usage documentation and the conversation path in the system diagram. GUI behavior, exports and saved report wording remain unchanged.

## Mechanical validation

`python3 -m unittest discover -s tests -q`: **302 discovered, 300 passed, 2 optional private-corpus tests skipped** (27.517 seconds). New regressions cover frozen-query equivalence and immutability; explicit, duplicate, mixed and foreign populations; main/child/shared accounting; unavailable children; streaming updates; missing, invalid and conflicting usage; metadata disclosure; guide delivery/reload/oversize handling; saved-run filtering/pagination; CLI queries; and clean extraction outside the checkout.

Existing CLI/MCP evidence-equivalence tests still compare the actual evidence exactly. Once-per-connection guide fields are checked separately, rather than being confused with source text. The extracted plugin returns the exact `SKILL.md` bytes/hash and exposes the new APIs. The final release archive uses the standard six-skill Claude plugin layout and excludes private stores, generated answers, logs, reports, screenshots and test fixtures.

## Observed Claude behavior

All runs used the approved installed Claude Code 2.1.295 host. The host reported `claude-sonnet-5-5`. These are real Claude executions against explicitly synthetic session evidence, not Ally data or a held-out evaluation. Every prompt, tested plugin snapshot, raw transcript and unedited answer remains under the ignored local `.analysis` directory.

| Local run | What was observed |
| --- | --- |
| `claude-conversation/run-kwjre6hd` | Loaded the conversation skill but compared normalized rows instead of inspecting captured usage. Misread “do not change saved judgments” as a reason not to open a query scope. Failed check retained. |
| `claude-conversation/run-1817j7rp` | Opened the scope, inspected sample captured usage and followed up on verification. Unnecessarily disabled child collection, skipped the writing skill and used “nothing ran” despite the missing child trace. Failed checks retained. |
| `claude-conversation/run-lxtpghgo` | Three questions completed; registered turn queries, raw-field inspection and unchanged saved judgments were verified. Child collection was preserved. The writing skill was skipped. A fabricated tool name was explicitly rejected by Claude Code before the valid read succeeded; no bypass execution occurred. |
| `claude-conversation/run-69rx138w` | All nine tool/delivery/preservation checks passed. Metadata-only accounting was followed by controlled excerpt inspection and a turn-specific query. The same conversation used computed totals and checked captured frames. See the semantic failures below. |
| `claude-frozen-questions/run-q9hesskp` | On a copy of a previously completed Claude investigation, the old write-measurement path correctly refused mutation; Claude then used read-only queries with `agent_id=main`. Saved run/record hashes remained identical. It skipped definitions, exposing another route that had missed writing-guide delivery. |
| `claude-frozen-questions/fallback-5d_eptiu` | Final first-data-call guide delivery was exercised with the native Skill tool disabled. All six checks passed: successful host, unchanged frozen records, explicit main-agent filter, captured-field inspection, both guides delivered and execution within policy. The answer correctly reported 80 cache-write tokens and a 120/240 = 50% cache-read token share from the synthetic four-response fixture. |

The final fallback run tested the final runtime and conversation skill; its package snapshot SHA-256 is `67f1173709df2f34f78b8c3cb9b37a4f01241006bf571a3ee1307cf26d9e1bf5`. Its conversation guide hash is `a3bebb1accaf4fd013b46d5caa5c28c05ebf603725a5e01816c78f64ce0e2629`. The shipped archive adds the final documentation/validation record. A source-accounting sample remains a sample, not verification of all provider usage.

## Semantic failures remain visible

The successful three-turn transport exercise was **not** a clean semantic-quality pass. In `run-69rx138w`, turn 2 falsely said that no assistant completion statement existed, because Claude had not read the final assistant message. After an explicit request to recheck its absolute claims, turn 3 read that message and corrected the assertion. It then still used language suggesting the assistant had not performed verification, even though the missing child trace only establishes that a verification result was not captured. The response also included unnecessary chronology and advice about rerunning the baseline to make a comparison “fair,” which was not necessary to answer whether the final revision was verified.

The guide now explicitly requires reading relevant ending landmarks before attributing or denying a completion claim and distinguishes an unsupported claim from proven nonadherence. That final wording was delivered in the final metadata-only fallback run; its effect on contextual diagnostic errors has **not** been established by another full semantic evaluation. Earlier output was not edited to make the feature look better.

The final frozen-query answer correctly labels its one-response inspection as a spot check and separates token share from request hit rate. Its statement that queries “don't change anything” is broader than the implementation: saved judgments are unchanged, while access receipts are retained. The audit hash checks refer specifically to saved runs and investigation records.

## Remaining limits

Conversation skills and accurate measurements cannot guarantee accurate interpretation or eliminate repetitive prose. Complete saved investigations should continue to use the managed independent-review workflow; ordinary chat answers do not automatically receive that review. Unseen-session evaluation, ambiguous intent and missing/shared child attribution remain necessary quality work. There is no superiority claim over `/insights`.

A new Claude connection needs the selected store and investigation ID (or explicit import selection). There is no automatic cross-store discovery, live session attachment or speculative Ally/Jira/CI connector. Current native import contracts and admitted snapshots remain the boundary. Other hosts and Ally compatibility remain unverified. This release made no presentation changes, so its new checks focus on CLI/MCP/Claude behavior rather than a new browser audit.

Local examples, deliberately excluded from Git and the distributable:

- [Unedited frozen-investigation answer](../.analysis/claude-frozen-questions/fallback-5d_eptiu/answer.md)
- [Frozen-investigation audit and exact package provenance](../.analysis/claude-frozen-questions/fallback-5d_eptiu/audit.json)
- [Three-turn raw results and checks](../.analysis/claude-conversation/run-69rx138w/result.json)
- [Incorrect turn-2 statement, preserved](../.analysis/claude-conversation/run-69rx138w/turn-2/answer.md)
- [Claude's subsequent correction, preserved](../.analysis/claude-conversation/run-69rx138w/turn-3/answer.md)
