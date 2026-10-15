# How the session analyzer works

The analyzer investigates one selected Claude Code session. It should help a developer understand the requested work, what the captured evidence supports, what remains unfinished and whether a specific change is justified. A report can correctly contain no recommendation.

## 1. Select and preserve the evidence

The operator can open `ally-session browse <directory>` to search parent logs, switch sessions and reopen each session’s latest saved analysis. Folder labels show the last two path components with the full path on expansion. Browsing and local previews do not call Claude; starting an investigation requires explicit controlled-excerpt approval. The operator can also select a log, native session file, directory or ZIP directly. The importer copies the source into a local store and records its identity. For a native parent session it also looks in that session's adjacent subagent directory. Only structurally linked children join the investigation. Missing children and unrelated captured files remain visible as coverage limits.

Instructions, code, test results or plugin versions from outside the trace enter only as explicitly admitted local snapshots. The snapshot records whether it is historical, contemporaneous or current. Today's skill file cannot prove which instructions ran in an old session. There is no speculative Jira, CI or Ally connector.

## 2. Compute facts before asking for interpretation

Python and SQLite reconstruct turns and join calls to results through recorded identities. Task requests include SDK submissions while human/user and inferred origins remain separately counted. An empty request denominator establishes no coverage. The engine calculates observed model responses, tool invocations, token categories, recorded execution durations and timestamp spans. Shared identities count once. Missing usage stays unknown. Cache reads and writes are components of input total; thinking remains inside output where the provider reports it that way.

A local evidence graph helps follow a tool to its result or a parent to a linked child. Cached literal search and direct source lookup work alongside the graph. It is an index for investigation, not a causal model or a proven model-speed improvement.

Context/cache views expose recorded compactions and before/after values. Large-result and repeat indexes help find evidence worth inspecting. Neither a cache drop nor a large result is automatically a problem. Captured bytes are not model-input tokens.

## 3. Claude investigates the task

The approved Claude host loads the investigation and writing skills. Managed processes close inherited stdin and receive only the explicit stage prompt. It first reads the main requests and follows material questions through scoped MCP tools. It can search and reread retained text in pages rather than receiving only a fixed summary. Common sensitive patterns are masked and excluded categories are disclosed. The system records the exact ranges delivered to the model; delivery is not proof of comprehension.

Claude authors the synopsis, outcome, requirement map, incidents, failure explanations and optional proposals. A requirement map connects material intent, corrections and scope changes to implementation, result, verification and revision evidence. Reading a request does not mark it complete. Claude must keep narrower retries, stale checks and unsupported completion claims qualified. Optional intent interpretations preserve competing readings; an ambiguous reading that changes the verdict stays unverified. A scoped next action can identify the check that would close a current gap without becoming a persistent recommendation.

Recovery episodes connect explicit attempts to the same intended result. Claude explains why an attempt belongs; the engine computes counts and associated usage from the selected identities. Expected test failures, correct denials, legitimate repetition and already resolved problems may need no fix.

Fault attribution asks which component and version the evidence actually implicates. A task can be unfinished while plugin fault remains unestablished. An immediate next action for the developer is distinct from a persistent instruction change.

## 4. A separate Claude process reviews the evidence

The managed runner saves the first conclusion as an immutable draft. A fresh review process rereads primary sources, supplies exact quotations and reviews the current record revisions. It can revise findings or continue unfinished inquiry. Earlier drafts and failed checks remain intact.

The reviewer checks separate obligation outcomes, opening consistency with the current requirement map, specific source explanations, distinct opening fields and status qualifications. A changed map invalidates the opening review bound to it. The engine checks identities, cited ranges, read receipts, calculations, required results, explicit semantic-check verdicts and current revision bindings. It does not prove that a quotation entails a claim or that a diagnosis is right. A shared time and money budget limits the workflow. Terminal host/API errors stop immediately; budget limits or incomplete inquiry remain explicit.

The interactive investigation skill alone does not automatically create the separate reviewer; use the packaged managed runner for that workflow.

## 5. Qualify changes before showing them as ready

Claude can recommend using a skill, narrowly editing one, creating a genuinely reusable missing procedure, changing CLAUDE.md, or another supported target. It must inspect the relevant version, scope and overlapping instructions. An ignored requirement is not a reason to add a duplicate rule.

Exact edits are checked against admitted targets. Applicable fixture checks are operator-run and tied to the proposal, target and plan. Claude cannot create a machine execution attestation through MCP. Readiness means the recorded prerequisites are satisfied; it does not prove future benefit or authorize applying an edit.

## 6. Render the saved report

The offline HTML report formats the saved data. It does not run a model, rewrite Claude's recommendations or improve its prose. Commands use literal command/argument fields while preserving the original masked record. Finding links use the saved descriptive titles; proposals remain in one place. The opening links to not-met and unverified requirements and unresolved findings. Compact requirement rows expand into full evidence. Every turn remains accessible; focused views use explicit evidence identities. Saved recovery sequences support direct input comparison, with scope and revision qualifications visible. A copyable handoff collates saved fields and references without another model pass.

A source click shows Claude's saved citation explanation or a matching saved review note, then separate input/result panes, cited text and surrounding context. If no explanation exists, the report says so. Copies use the exact retained masked text, even when the display wraps lines, adds gutters or shows only an excerpt. Main, child, combined and analyzer usage remain separate.

The developer reviews the evidence and chooses what to do. Nothing in the report automatically changes a skill, file or configuration.

## What makes it useful—and what remains unproven

The useful output is a specific supported account of the task, unresolved work and a falsifiable action when warranted. Counting failures or producing fluent advice is insufficient. The current checks make unsupported claims easier to detect; they cannot guarantee an insightful or error-free diagnosis.

The next quality gate is the independent evaluation already specified: unseen sessions, independently labelled outcomes, identical evidence for the comparison, blinded usefulness review and checks of rejected as well as accepted recommendations. Existing guided examples do not establish superiority over `/insights`.

See the [system diagram](session-analyzer-product-design.md), [governing spec](single-session-investigation-spec.md), [release audit](release-audit-0.11.0.md) and [evaluation protocol](investigation-evaluation.md).

The [developer usefulness audit](developer-usefulness-audit-2026-10-15.md) identifies observed semantic and presentation gaps without changing Claude’s reports.

Thinking content has a separate local source-view path. The report can display captured masked thinking when source export is enabled, while model evidence reads retain their thinking-exclusion policy. Structured availability metadata distinguishes an empty captured field, missing text, provider redaction and unsupported formats. Response-wide usage remains reconciled once across its source records. Neither an empty excerpt nor planning text proves execution.


The 0.12.0 session library wraps that renderer with a single header, grouped session sidebar and horizontal report navigation. It chooses one latest saved analysis per stable session identity; prior outputs remain immutable internally. Payload and child-metadata comparisons drive freshness independently of investigation completeness. Updates use the same managed Claude workflow and preserve access to the saved report while running or after a failure. Search, folders and reading position survive session navigation. See the [navigation validation record](release-audit-0.12.0.md).
