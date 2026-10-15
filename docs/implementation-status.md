# Implementation status — 0.14.1

Expanded source lists retain their icon/count and replace numbered placeholders with short literal captions. Saved explanations, tool descriptions, file/command fields and task-notification summaries identify the record; quieter metadata distinguishes input/result, turn or child, and time. Long captions are bounded with full wording on hover and in the source inspector. Unknown or ambiguous metadata does not generate a description or a judgment. Exact citations, source copies and Claude-authored report data remain unchanged.

Twenty-eight relevant checks passed, including seven new caption regressions. The real migration report was checked on desktop and at 390 pixels; keyboard navigation, exact copying and current-renderer HTML export passed. This presentation change does not require or claim a new Claude investigation. See [validation](validation.md).

---

# Implementation status — 0.14.0

Turn/finding links now state their evidence relationship and open the canonical finding at the selected turn's retained record. Roles come from explicit saved associations or the recorded outcome of an already-linked tool result; absent roles remain Related evidence. Multiple records have a selector. Full finding, source/context inspection, exact copying and saved review qualifications remain accessible. Filters name the selected finding, counts distinguish findings from linked turns, and the library title compacts while reading with an accessible expansion control.

Future Claude investigations can save distinct same-goal episodes within one evidenced pattern. Nested episodes receive existing verification, revision, chronology and structural-child checks. The report exposes the unfinished episode directly, folds recovered supporting episodes, and counts associated resources over deduplicated identities. Claude still justifies membership and causal claims; shared tool names do not establish either. Writing/review guidance separates the opening fields and targets specific unresolved questions.

The real migration report and labelled synthetic pattern/source-excluded examples passed the browser checks described in [validation](validation.md). Existing F2 and all Claude-authored wording are unchanged. The future pattern workflow has mechanical coverage but no fresh Claude-run validation in this release; historical grouping and repetition need a Claude-authored revision, and independent diagnostic evaluation remains outstanding.

---

# Implementation status — 0.13.4

The turn table uses compact F1/F2 references instead of repeating long finding titles. A shared key above the table shows each unchanged saved title and its linked turns. Selecting linked turns filters the chronology; every reference opens the existing full finding directly. Identical titles keep distinct identities, and findings without attributed turns remain accessible. Requests gain the freed column width. Presentation, identity/payload regressions, packaging and desktop/narrow browser checks passed; see [validation](validation.md).

---

# Implementation status — 0.13.3

Turn findings use a wider responsive column and display their entire saved titles. Requests retain the larger text column; narrow views scroll the table instead of squeezing either column. Multiple findings stay separate and open their existing complete detail dialogs. The supplied migration report was verified on desktop, with the source inspector open, and at 390 pixels, including keyboard access and full requests. See [validation](validation.md).

---

# Implementation status — 0.13.2

Turn numbers and call counts stay on one line and align consistently. The turn-number column has sufficient space for multi-digit ordinals; narrow layouts preserve table scrolling. Saved values and source data are unchanged. The affected migration report and existing presentation/package checks passed; see [validation](validation.md).

---

# Implementation status — 0.13.1

Source-panel wrapping and copying now share vector icon sizing, stroke weight, color and button dimensions. A compact tooltip uses the report palette, and a restrained tint identifies enabled wrapping. The action labels, keyboard accessibility, per-panel wrap state and exact copying are preserved. This presentation-only patch leaves saved source data and Claude-authored analysis unchanged. See the latest [validation entry](validation.md).

---

# Implementation status — 0.13.0

The opening now exposes saved not-met/unverified requirements and unresolved/unknown findings, with an optional saved next check. A compact requirement table separates intent, status and result evidence. Finding/source links use saved descriptive wording; every turn stays in the chronology, with explicit evidence-based focus controls. Recovery attempts have a connected sequence and a direct input comparison. Copy remaining work collates inspectable saved text, scope, checks, gaps, review qualifications and source identities without generating a new recommendation.

The investigation contract now accepts competing intent interpretations and optional immediate next actions. Declared ambiguity that changes an active requirement's outcome cannot accompany a confident completed/not-met verdict. Review guidance distinguishes explicit prerequisites from inferred sentence order. These rules cannot discover every ambiguity or establish diagnostic quality by themselves. Historical Claude prose remains unchanged.

Final backend validation discovered 247 tests: 245 passed and two optional private-corpus tests were skipped (23.701 s). Browser checks cover actual saved migration/CSV/TTLCache reports and a labelled synthetic recovery example, including exact copying, current-layout HTML export over unchanged saved data, JSON bytes, complete chronology, requirement navigation and 390-pixel layouts. The spec, diagram and plugin package were updated.

Both fresh Claude checks hit the account session limit before review completed. Their unedited drafts and failures are preserved. One draft still contains unsupported claims, so this is not a passed diagnostic-quality release or a claim of superiority over `/insights`. See [release audit 0.13.0](release-audit-0.13.0.md) for observed behavior and the outstanding review/evaluation work.

---

# Implementation status — 0.12.1

The source inspector now uses the supplied state-specific word-wrap icons. Hover and keyboard focus show the exact next action: “Enable word wrap” or “Disable word wrap.” Each source panel retains its own wrap state, accessible pressed state and exact-copy behavior. Saved report content and investigation behavior are unchanged. The existing presentation, source-content and packaging checks pass; browser validation is recorded in `validation.md`.

---

# Implementation status — 0.12.0

The session library now uses one collapsible, folder-grouped sidebar and one application header. A session opens its latest saved analysis with one selection; internal report revisions remain immutable but have no history/version controls. Native titles, literal request previews, full-path disclosures, search, recent activity, horizontal report navigation and Findings reuse the existing data and renderer.

Freshness compares captured record identities and linked-child metadata. It is separate from investigation completeness and task outcome: new activity can coexist with an incomplete investigation, and Ready means completed analysis of matching captured evidence. Unknown comparisons, changed evidence, running jobs and failed updates have explicit labels. Updates retain the saved report, enforce the existing disclosure/budget workflow and reject duplicate jobs or invalid report replacements.

The backend run executed 234 tests successfully and skipped two optional private-corpus tests; both optional tests then passed with the local supplied corpora. Browser checks exercised real saved reports, a real Claude regeneration, labelled success/failure fixtures, exact exports/copying, source inspection, session navigation and the narrow-screen drawer. The actual Claude run used the immutable 0.11.2 investigation snapshot captured before the presentation release was bumped; it completed with zero recommendations and unedited saved prose. The final navigation/presentation package is 0.12.0. See [release audit 0.12.0](release-audit-0.12.0.md).

The work does not establish large-library performance, Ally compatibility or independent diagnostic quality. Idle source discovery uses explicit Refresh; it is not a filesystem watcher. Older reports can lack metadata needed for a confident freshness comparison. No `/insights` superiority claim is made.

---

# Implementation status — 0.11.2

Thinking-only assistant records have a distinct source role. The inspector shows specific empty/missing/redacted/unsupported/omitted states, retains identity and response-wide usage, and suppresses empty code controls. Explicit local source exports can display captured masked thinking; investigator evidence reads still omit it. Existing projections, source hashes and Claude-authored judgments remain intact. Empty or whitespace-only claim references are rejected.

The supplied screenshot's record contains an empty thinking field. Its response has 359 inclusive output tokens shared across two captured records; separate thinking tokens were not reported. No text or token count was reconstructed. Validation covers mechanical regressions and browser behavior, not a fresh Claude investigation.

---

# Implementation status — 0.11.1

Presentation-only update: expand/restore and collapse/reopen source inspection. The retained selected record, wrapping and scroll state survive collapse. Desktop expansion and narrow screens use accessible modal focus; side-by-side reading remains available. Existing saved analysis is rendered without re-investigation or prose edits. See the latest validation entry for browser and package checks.

---

# Implementation status — 0.11.0

A local session library now opens a selected Claude directory, filters folders using their last two path components, searches requests/IDs/paths, opens uninvestigated local logs, and switches saved report versions. Full paths remain available. Launching a Claude investigation is an explicit separate action through the existing managed runner and budget/disclosure controls. Historical reports and model output are not rewritten.

Task accounting now includes SDK submissions without relabelling them human-origin turns. Empty request populations do not claim complete coverage. New managed reviews require explicit semantic checks for separable obligations, evidence-supported completion, opening/map consistency, specific citation explanations, field purpose and status qualifications. Map revisions invalidate prior opening reviews. The report shows saved qualified or disputed judgments next to their subjects.

Mechanical tests and actual Claude observations are recorded in [release audit 0.11.0](release-audit-0.11.0.md). Semantic checks are model judgments, not deterministic proof. The library does not add Ally connectors, cross-session conclusions, automatic recommendation application or a quality score. Extra artifact snapshots remain available through the existing managed CLI's explicit manifest; the browser currently investigates the selected trace and linked children.

---

# Implementation status — 0.10.4

The managed Claude process now receives only its explicit stage prompt: inherited stdin is closed. The new regression exercises the real parent-pipe boundary. This corrects a workflow exposure discovered while generating a native synthetic coding session; the contaminated attempt remains saved.

205 backend tests pass with both supplied corpora. Fresh investigation/review runs completed for citation explanations and a native Claude Code CSV session. The latter used the default unanchored question. Both saved zero recommendations and retained all revisions. Executed tools stayed within policy; unavailable tool-name attempts were rejected and remain visible.

This is a locally testable plugin candidate, not a claim of broad production readiness. Live review still accepted a bundled completed requirement with a missed sub-instruction. SDK requests remain excluded by the current user-turn policy, so this example has zero reconstructed user turns. See the [release audit](release-audit-0.10.4.md) and [developer usefulness audit](developer-usefulness-audit-2026-10-15.md). The report design and saved historical outputs are unchanged.

---

# Implementation status — 0.10.3

The selected command-row design is implemented with Findings retained. The renderer extracts only recognized native envelopes into literal command/argument fields, keeps nonredundant message text and provides full-field copies and original masked-source access. It does not summarize ambiguous wrappers.

Citations can carry Claude's one-sentence explanation. The engine requires inspected evidence; the inspector preserves that wording, or an exact-owner saved review note and verified quote. Missing explanations are explicit and adjacent source navigation clears prior claim context. Source opening uses the triggering control to preserve desktop position; narrow views retain modal/focus behavior. Existing metrics, failure explanations, subagent drill-downs and exports remain.

The standard plugin now ships `scripts/ally-session.py`, five Markdown skills and a reproducible allowlisted ZIP. Both its clean extraction and the installed Claude manifest validator pass. The managed runner stops on terminal host/API errors and preserves the actual cause rather than attempting another reviewer.

Two backend passes completed: 202 tests before the release regressions, then 204 with both optional private corpora enabled. Browser checks, actual Claude observations and remaining work are separated in the [release audit](release-audit-0.10.3.md). The fresh 0.10.3 model run is blocked by expired OAuth; plugin/MCP loading succeeded, but that is not a passed model-behavior check. Earlier successful Claude outputs remain unchanged. No Ally compatibility or `/insights` superiority is established.

---

# Implementation status — 0.10.2

October 14, 2026. The single-session workflow now connects material requirements to inspected result evidence, declared verification scope and artifact revisions. Maps preserve corrections, merged intent, withdrawal/supersession, missing evidence and immutable versions. New managed runs require a map; reading every request is still separate from finding every requirement or fulfilling it. Requested response content has an explicit evidence path, so a writing task need not invent tool execution or user acceptance. Execution claims still need execution evidence.

Recovery episodes extend existing incidents. Claude justifies the goal and membership of distinct attempts; code validates identities and computes their union. All five token components, calls and explicit execution durations remain separate from per-agent observed intervals. Shared response usage and overlapping episodes are disclosed. Expected failures, legitimate repetition, correct denials and recovered work can require no change.

The context/cache timeline reuses reconciled responses and recorded lifecycle events. Registered formulas provide peak input, matched-population cache share, before/after input and percentage-point differences, explicit compaction duration and captured tool-result bytes. Timeline and repeated-retrieval pages stay bounded, with full retained identities and text available through continuation. Input drops alone do not create compactions; bytes do not become model-input tokens. Detailed report views sit behind Metrics, turns, child invocations and findings.

Optional fault attribution identifies component/version, historical versus current evidence, instruction adequacy, execution/handoff evidence and missing children. It separates immediate task action from a justified persistent change. These are Claude judgments with mechanical prerequisites, not a causal classifier. A local artifact manifest reuses existing snapshot admission; no speculative Jira, CI, Ally or internal-plugin connector was added.

The governing specification and validation record describe the implementation and observed development cases separately. The final mechanical suite passed 197 tests with both private corpora enabled. Actual Claude runs exercised requirements, revision checks, recovery, registered resource formulas and attribution. All original outputs and failed attempts are retained. The supplied-log investigation is still the preserved 0.8.1 run, rendered with the latest UI and deterministic resources; no new requirement map was fabricated for it. The new model-facing fields are demonstrated in explicitly synthetic development sessions.

Remaining limits: semantic diagnosis and requirement completeness are not certified; representative Ally schemas, historical component artifacts and authenticated retrieval await laptop access. Active-time/concurrency/critical-path claims need telemetry not currently captured. Held-out quality, recommendation benefit and a matched `/insights` comparison remain unmeasured. See [validation](validation.md) for exact observed behavior and negative checks.

---

# Implementation status — 0.9.0

The offline report now has compact section navigation and a source inspector beside the document, with a full-width inspector on narrow screens. Known command/JSON/file-source formats receive restrained lexical coloring; unknown languages remain plain text. Copy controls use the saved masked string, never line numbers, highlighting markup or a model rewrite. Long records have explicit full access, wrapping and scrolling. Input total, uncached input, cache creation, cache read and output are visible in metrics and turn/child details. Combined and analyzer usage remain separate.

The managed workflow's 0.8.1 request map ensures all main user requests are read; this is exposure coverage, not a requirement-completion ledger. That distinction remains a diagnostic limitation. See the current validation record for the completed scoped rerun and remaining unknowns.

---

# Implementation status — 0.8.0

October 14, 2026. The managed runner now uses separate investigation and evidence-review Claude processes within a shared time/money budget. First-pass finish calls save drafts, rather than freezing an unfinished analysis. The review host can continue inquiry and revise attributed records. Exact source quotes must match retained text and have fresh review-stage read receipts. Current record versions and the final draft require checks before finalization. The engine does not claim to validate their semantic accuracy.

Incidents now support explicit immutable revisions; active findings use the newest linked version, while history remains in the report. Previously identified available sources cannot be erased from an inquiry plan to close it unread. A missing-evidence stop cannot disguise open investigation work in the managed workflow. Search history and recent parent input/result IDs are exposed as navigation aids. Failure counts remain invocation accounting, not a complete inventory of task failures.

The restricted runner is shipped as `ally-session investigate`. Interactive slash-command use remains supported but does not create the independent review host automatically. No analysis prose is rewritten by the renderer or Codex. See validation history for the observed model results and limits.

---

# Implementation status — 0.7.0

October 14, 2026. Single-file imports collect adjacent native child logs and sidecars. Structured links admit children recursively. The document keeps main-agent metrics and source records in view, with child evidence, separate usage, nested invocations and failures behind invocation controls. Missing traces, resumed/shared histories and uncertain completion remain explicit. Combined accounting and Claude-authored output are preserved.

## 0.6.0 failure explanations

October 14, 2026. Counted failure drill-downs now show saved model explanations of the attempted action, observed failure and follow-up. Scoped discovery and append-only explanations have read-receipt, original input/result and later-success prerequisites. Unknown recovery, incomplete evidence, missing explanations and earlier revisions remain visible. The renderer preserves every authored word and retains full evidence/context navigation. The offline click makes no model request.

These checks establish evidence prerequisites, not whether a cited success resolves the same problem or whether a causal explanation is correct. The workflow asks Claude to explain every counted attempt and preserve partial status when resources prevent doing so. Mechanical and actual-host validation is recorded in [validation](validation.md).

## 0.5.1 foundation

October 14, 2026. Nonzero recorded-failure counts now open the invocations counted by that turn pattern. Each entry retains its turn, recorded status, result preview and links to full source input/results; turn links open context. Zero counts remain noninteractive. The counting definition and saved Claude output are unchanged.

## 0.5.0 foundation

October 14, 2026. Added a document report and stronger diagnostic prerequisites. The original single-session scope, metrics, disclosure controls and candidate execution rules remain.

- Versioned inquiry revisions and primary-result/read-receipt prerequisites distinguish available unread evidence from unavailable evidence. Original tool inputs/results can be read together per turn. These checks do not certify semantic support or prevent every premature model stop.
- Claude saves a short title, one-to-three-sentence synopsis, separately qualified observed outcome and explicit stop basis. The renderer preserves its exact wording. There is no Codex output editing stage.
- Recognized literal missing-child counts are compared with distinct captured missing-child identities. Discrepancies remain visible without rewriting the source sentence; other prose quantities and semantic scope are not certified.
- Existing-skill invocation, narrow skill edits, new skills and CLAUDE.md are supported with current snapshots, declared instruction inventory/scope/overlap review, exact edits or invocations and derived file growth. Missing evidence cannot become readiness; ignored requirements cannot justify duplicate additions.
- Flat HTML report: compact metrics, turn requests/calls/findings, expandable source context, proposals once, exact-copy controls, local HTML/JSON export and expandable patterns/coverage. Long text is preserved behind literal previews. Source embedding is explicit and does not inflate model exposure.
- Legacy investigation records retain their original policies; zero recommendations, no justified action, insufficient evidence, incomplete and not-run states remain distinct. All validation and revision history remains available.

See [validation](validation.md) for every actual run and remaining failure. Both 0.5.0 supplied-session runs read primary test results but stopped early by choice. The later run also misstated the missing-child count; the final report flags the discrepancy and preserves the sentence. The long-result smoke test attempted a nonexistent tool before using the correct reader. No held-out superiority claim is made.

---

# Implementation history — 0.4.0

October 14, 2026. The single-session mechanics are implemented. Held-out diagnostic quality, recommendation benefit and a model-level graph comparison remain unproven. The [usage guide](single-session-usage.md), [PM design](session-analyzer-product-design.md) and [governing specification](single-session-investigation-spec.md) describe the workflow.

## Delivered in 0.4.0

- Immutable selection of one root session and structurally linked captured children, explicit missing/unlinked traces, versioned source scope, and scoped MCP enforcement. Legacy APIs cannot bypass a bound host.
- Session/per-turn response and tool counts, token accounting, explicit duration versus timestamp span, request-origin/attribution coverage, and a descriptive turn-pattern table with counts, medians, defined shares and separate failure counts.
- Compact turn navigation with paged underlying identities, cached literal search, bounded SQLite evidence relationships, individual/batched source reads and continued rereading. Text versions/fingerprints and delivered ranges are recorded; original source records remain intact.
- Separate incidents, claims and computed selections. Optional recommendations, distinct expectedness/resolution/diagnosis/action fields, and independent run status and conclusion. Calculated claims validate against saved measurements. A narrow numerical-unit lint is a warning/check mechanism, not a universal prose verifier.
- Operator-selected artifact snapshots and linked scope revisions. Required target inspection, candidate bindings, falsifiable plans, attributed contextual review and derived recommendation readiness. No model-writable machine attestation API.
- Operator-only prepared fixture execution with positive, negative, syntax/schema and target-contract checks as applicable. Exact candidate, proposal, fixture, plan and executable identities are recorded; unavailable/not-run/failed checks cannot pass. These tests establish only the fixtures' assertions. The temporary directory is not an OS security sandbox.
- Exact Claude prose preserved in HTML/JSON, including partial runs and all candidate revisions. Host usage and provenance are distinct from source-session usage. A shared writing skill guides Claude; no external output-editing stage exists.
- Backed-up transactional SQLite migration; existing analyses and legacy insights remain readable under their original contract. The engine remains standard-library-only and has no network/model client or Jev integration.

## What the tests establish

Offline regression coverage includes scope escapes, duplicate identities versus retries, missing children, ambiguous/overlapping attribution, cache components, duration semantics, bounded pages, Unicode retrieval, projection-version stability, denied disclosure, graph cycles, numeric claims, target changes, genuine behavioral fixture counterexamples, forged attestations, exact rendering and migration rollback. Real subprocess tests exercise CLI and bound MCP transport. Counts and final package checks are recorded in [validation](validation.md).

The synthetic fixture runner now tests different positive and negative behavior, including an overbroad matcher and a verifier that misses an alternate error code. It is not a native hook adapter or proof that any arbitrary operator-authored fixture adequately tests a proposal.

The source-log development runs exposed oversized turn pages and premature model stopping. Pages now keep compact metrics and expose full membership through pagination. The skill asks Claude to follow material available evidence, distinguish launch from completion and abstain only for the actual missing evidence. All earlier outputs and errors remain preserved; these development changes are not a held-out quality result.

## Remaining limits

- The engine checks identities, quantities and declared check results. It cannot establish prose entailment, instruction applicability, diagnosis or causal benefit; those remain attributed model judgments.
- Current target snapshots cannot establish historical state. New-skill overlap and prompt applicability depend on the available sources and model review. The analyzer cannot detect an unadmitted target change in the user's filesystem.
- Native Ally gate profiles, authoritative task-success evidence, external transport/billing telemetry and representative capacity tests remain pending. Cross-session investigation is deferred.
- Acceptance cases T01–T28 include model behavior requirements. Mechanical regression coverage is not a claim that all 28 passed live semantic evaluation. A held-out, independently reviewed study is still required before claiming superiority over `/insights`.
- The local mechanical retrieval benchmark reports cache gains for this synthetic workload; one-hop graph traversal was slower than a direct indexed lookup. There is no measured graph advantage for end-to-end Claude investigation.

---

# Implementation history — 0.3.0

October 13, 2026. This records the runnable implementation, separately from the broader draft specification.

## Trajectory retrieval — 0.3.0

- `search_trajectory` searches a retained text projection locally, beyond preview truncation. It includes tool inputs, queued prompts, text attachments and nested progress data. Literal matches return snippets, source references and character positions. Session/agent filters and a scan cursor make scope explicit; a partial empty result is not proof of absence.
- `read_trajectory_event` pages through the same masked text, without model summarization. Total length, offsets, fingerprint, omission notes and adjacent event IDs support continued reading. The original source records remain intact. Thinking, media, environment payloads and other raw metadata are outside this text view.
- Both tools follow the existing operator disclosure policy. CLI equivalents explicitly disclose text locally. The investigation skill checks available earlier/later evidence and can reread as needed, within a user-specified budget; it has no fixed total reread count.
- Eight regression tests cover complete reconstruction of long Unicode tool inputs, late matches, search pagination, scope isolation, navigation, masking, omitted payloads, disclosure policy, wrong fingerprints, CLI/MCP agreement and immutable canonical results. Search uses a local scan, not a full-text index; large-corpus retrieval performance is unmeasured.
- A source-checkout runner invokes the shipped Claude workflow on an explicitly selected input and preserves its complete output. It checks saved recommendation bodies against Claude's tool calls and the HTML against the standard exporter. The visible supplied-log example now comes from this path, with no Codex edits or supplied topic/event anchors. External evaluation stays separate from output.

## Writing addition — 0.2.1

- A shared `write-report` skill guides the three existing workflows. It requires specific evidence, concrete changes and checks for later recovery or already completed fixes. It removes unsupported benefit claims, generic coaching and repeated prose; it is not an automatic factual verifier.
- Investigation HTML presents proposed actions and observations first, keeps material uncertainty visible, and puts supporting reasoning and provenance in expandable details. Source line labels replace long event IDs in the main readout; full IDs and source member references remain in the details.
- The opt-in synthetic Claude host test checks actual invocation of the writing skill. The supplied-log demonstration and evidence review remain private local artifacts outside the distributable package. See `writing-quality.md` and `validation.md` for scope and limits.

## Investigation addition — 0.2.0

- A third `investigate` skill uses the approved Claude host to inspect contextual evidence, recovery, counterevidence and alternative explanations, then propose concrete changes with follow-up measures. The analyzer has no model client and no new provider dependency.
- Bounded before/after context is scoped to one session and agent. Metadata is the default; selected text requires the existing operator disclosure policy and an explicit request. Common secrets are masked; thinking, media and environment fields are excluded. Masking is incomplete and windows do not certify task completeness.
- Suggested insights, caller-reported model/skill provenance and append-only operator reviews are stored outside canonical analysis. Evidence IDs, finding IDs and structured metric values are checked; prose and causal claims are not validated.
- Separate offline investigation HTML/JSON exports display observations, proposed explanations, alternatives, recommended changes and follow-up measures. The canonical metrics report remains available unchanged.
- The new tools are `get_investigation_context`, `save_insight`, `get_insights`, and `export_investigation`. CLI equivalents support local use and operator review.
- A held-out human evaluation is still required before claiming improvement over `/insights`; see [the evaluation protocol](investigation-evaluation.md). Automatic episode reconstruction, matched-cohort comparisons and Ally gate adapters remain future work.

## Delivered

- Python standard-library engine and CLI; SQLite local store, immutable source snapshots and stable evidence references.
- ZIP/directory/JSONL/`.log` imports, limits, unsafe-entry rejection, malformed-line diagnostics, duplicate handling and conflicting-identity qualification.
- Native 2.1 transcript adapter exercised with 20 observed versions, including the supplied Ally 2.1.190 export. Compatibility claims apply to observed shapes, not every feature in each version.
- Per-response token reconciliation, input cache categories, optional thinking counts, explicit cost rate cards, request-ID observations, and separate non-additive child/cost summaries.
- Tool call/result joins with success, launch acknowledgment, permission denial, user rejection, interruption, timeout, validation failure, execution failure, verification-command failure, unknown, unresolved and conflict outcomes.
- Explicit tool and turn durations. Timestamp intervals are shown separately and never called execution latency.
- Agent metadata/child links when present; missing child traces and parent links are visible. Session chronology and parent UUIDs are retained; no inferred critical path.
- Interactive, offline HTML report with batch/session scopes, searchable sessions and activity, agent filters, findings, coverage, source-line inspection, and JSON/CSV export. CSV contains session summaries; JSON contains the detailed normalized analysis.
- MCP stdio server with validated arguments, bounded/paginated queries and background import/analysis/export jobs. Only one write job runs per server. Live progress is in memory; completed jobs persist. A previous process's incomplete job is reported as `owner_not_connected` rather than silently marked successful.
- Claude Code manifest, MCP configuration and four namespaced skills. The engine does not call a model; approved agents can explain computed results. Human review notes use a separate table and do not mutate canonical results.

## Rule boundaries

| Rule | Implemented condition | Limit |
|---|---|---|
| R01 | Same tool, exact canonical arguments (excluding shell description), captured result and failure outcome at least 3 times within 10 model steps in an agent run | No semantic normalization of variable error messages; may miss equivalent failures |
| R02 | Exact contiguous 2–5 call/result pattern repeated 3 times within the step window | No assertion that external artifact state was unchanged |
| R03 | Identical status results from `Monitor` or a narrow shell monitoring heuristic recur | Notice only; authorized monitoring is legitimate |
| R04 | Successful native Edit replacements have matching inverse string/file hashes | Reports inverse replacements, not proof that complete file state moved A→B→A |
| R05 | Input above 200,000 reported tokens or captured result above 65,536 bytes | Configured review thresholds, not model limits or token estimates of tool text |
| R06 | A failed tool has no later successful invocation with identical tool/arguments in that agent run | Different repair paths remain unknown; not proof an issue stayed unfixed |
| R09 | Missing/conflicting tools or usage, missing named child logs, malformed input and missing parent links | Does not certify global trace completeness |

R07 (completion claims) and R08 (Ally pipeline contracts) are explicitly unavailable. A new rules profile requires structured evidence and validation against the deployed Ally agentset. Prose documents are reference material, not executable policy.

## Supplied Ally session

Source fingerprint: `a3c03a876eebca9bed36ea75a0c601534440370f3c0c1f6fd0971a144fce8741`. The source remains outside the repository and distribution package.

| Observation | Result |
|---|---:|
| Parsed records / malformed lines | 3,569 / 0 |
| Native version / observed sessions | 2.1.190 / 1 |
| Eligible model-response identities | 806 |
| Explicitly recognized synthetic quota notices | 3 |
| Tool calls / matching results | 773 / 773 |
| Error-marked results | 15 |
| Execution failures / validation failures / user rejections | 6 / 5 / 4 |
| Background launch acknowledgments | 13 |
| Named child traces absent from this file | 16 |
| Uncached input tokens | 1,612 |
| Cache creation input tokens | 14,699,387 |
| Cache read input tokens | 386,423,782 |
| Inclusive output tokens | 517,079 |

All four token fields cover the 806 observed eligible response identities. These are parent-trace subtotals, not all delegated-agent spend. Thinking blocks exist, but separate thinking-token counters do not. No provider request IDs or transport-attempt telemetry are present. No rate card was supplied, so cost remains unpriced.

Three quota messages reuse `msg_token_limit` with regular model names. A narrow adapter rule recognizes the observed 2.1.190 sentinel, explicit zero usage, absence of request ID, and quota-message shape; it preserves three separate notices and excludes them from model-response accounting. Unknown shapes are not automatically excluded.

## Pending product work

- Actual Ally pipeline profiles, gate/artifact freshness evidence, and independently verified completion outcomes.
- External API attempt/retry telemetry adapters and reconciliation against authoritative billing.
- More native-format regression fixtures, Windows/Linux host testing, and representative 2 GiB performance testing.
- A hand-labelled loop dataset and precision/false-positive measurements. Exact-match unit tests are not a precision study.
- Automatic retention/per-dataset purge, crash-resume jobs and full graph visualization. Model interpretations now have separate persistence with caller-reported model/skill provenance; that provenance is not independently attested.
- Expected-negative tool semantics need explicit tool/task profiles. For example, a search command's exit 1 remains a recorded execution failure with no claim that it harmed the task.

Only the installed Claude Code version and current macOS workstation are integration-tested. See [validation results](validation.md) for measurements and limits.
