# Validation — 0.13.1 source controls

October 15, 2026. Twenty existing presentation, source-content and clean-package tests passed in 1.188 s. The wrap glyphs now use locally drawn SVGs through the same offline icon pipeline as Copy; the cropped PNG assets were removed. No new model run or authored-output revision was needed.

In the native TTLCache report, both buttons measured 28 × 28 pixels with 18-pixel icons and identical plum color. Both action labels, pointer/keyboard activation, Escape dismissal and retained wrapping after inspector collapse/reopen were checked. Wrapping reduced the 759-character record from 5,996 pixels of horizontal content to its 312-pixel viewport without changing its text. After the copy completion feedback, the browser clipboard matched all 759 characters exactly. At 390 × 844 the inspector had no horizontal overflow and the tooltip stayed within the viewport. The tooltip uses 12-pixel text, a 4-pixel radius, warm-white surface and the report's border/text colors. Screenshots are retained in `.analysis/wrap-refinement-0.13.1/`.

---

# Validation — 0.13.0 developer reading flow

October 15, 2026. The final suite discovered 247 tests in 23.701 s: 245 passed and two optional private-corpus tests were skipped. New regressions cover all-turn chronology, saved descriptive labels, open-state distinctions, explicit turn identities, unchanged payloads, review scope, ambiguity admission, optional next actions and recovery comparison. Existing token, timing, narrower/stale verification, denial, expected failure and child-evidence checks remain in the suite. Output: `.analysis/developer-flow/backend-final.log`.

Browser checks used the supplied 32-turn migration report, native CSV/TTLCache coding reports and an earlier completed Claude review of a labelled synthetic recovery trace. All turns remain accessible; the migration's focused selection showed six explicitly linked turns. Requirement rows, original review assessments, recovery inputs/results, source collapse/reopen, keyboard copy and narrow-screen layouts were exercised. The final TTLCache handoff copied all 6,254 characters exactly and contained one map-level review. Browser-downloaded JSON matched saved bytes; HTML matched the current renderer and preserved its embedded report payload. Original HTML remains retained. Receipt: `.analysis/developer-flow/export-check-final.json`.

Desktop and 390 × 844 captures are retained under `.analysis/developer-flow/`. The report had no outer horizontal overflow at 390 pixels; recovery columns stacked and source inspection retained its selected identity. Plugin-manifest validation, packaging checks and JavaScript syntax validation passed. These are implementation checks, not an accessibility certification or semantic-quality benchmark.

Two fresh approved Claude investigations on the new investigation/review skills stopped at the host account session limit. Both saved drafts but no final reviewed conclusion. All model output and revisions remain unedited. The native CSV draft still had an unsupported missing-report claim and a bundled completion judgment; the synthetic trace produced a source-backed next-action field, but review did not complete. [Release audit 0.13.0](release-audit-0.13.0.md) records run identities, costs, evidence and outstanding work. No independent `/insights` comparison was run.

---

# Validation — 0.12.1 word-wrap controls

October 15, 2026. Nineteen existing presentation, source-content and packaging tests pass (`.analysis/wrap-control/checks.log`). The final report JavaScript passes Node syntax validation. In the in-app browser, the saved CSV report switches between the supplied off/on icons, with the exact “Enable word wrap” / “Disable word wrap” tooltip messages. Pointer activation, keyboard focus/Enter, Escape dismissal and long-line wrapping were exercised. The long source changes from 5,120 pixels of horizontal content to 311 pixels within a 311-pixel viewport. Full screenshots are retained in `.analysis/wrap-control/`. Claude-authored text and saved source values were not edited; this presentation change requires no new investigation.

---

# Validation — 0.12.0 session navigation

October 15, 2026. The new library shell renders existing saved report data without changing Claude-authored fields. Stable session identities, full-path folder grouping, latest-analysis selection, freshness/completeness separation, linked-child revisions, failed-update retention, invalid-output rejection and embedded payload equality have mechanical regressions. The final backend run reports 236 discovered tests, 234 passes and two optional skips. Those two private-corpus cases then pass separately. Logs: `.analysis/navigation-0.12.0/backend-final.log` and `private-corpora.log`.

An actual Update analysis action completed through the approved Claude workflow for the native CSV development session: job `8144cbf91dbb406499ca264cca8d8d5e`, report `01482b928b534216b1e3538fa9941b33`, 16:05:10–16:12:40 UTC. Its origin/transport audit passed, investigation and independent review ran, zero recommendations were saved, and all saved authored fields match Claude's tool inputs. Reported stage costs total $1.9007928. This run used the frozen 0.11.2 investigation snapshot created before the package version bump; the final report is displayed by 0.12.0. It validates the update path, not held-out diagnostic quality.

In-app browser checks cover the real CSV, TTLCache and supplied migration reports plus seven explicitly labelled navigation fixtures. Success updates one visible report; controlled failure keeps the old report and names the failed update; a running job disables duplicate work. New activity and incomplete investigation appear together. Identical titles in identical abbreviated folders retain separate full-path identities. Search, disclosures, one-click selection, browser Back, list position, source expansion/collapse and keyboard dismissal were exercised. Final history handling replaces iframe navigations to prevent an extra Back step; hidden drawers do not overwrite the retained list position.

Downloaded JSON and HTML are byte-identical to their original saved files (`export-checks.json`). Exact source copying was verified by pasting all 759 saved characters; presentation line numbers and wrapping are excluded. Existing token populations and all five categories remain visible. The TTL example shows 69,698 inclusive input and 5,526 output tokens; the supplied migration retains 16 unavailable child traces. A source control's viewport position differed by 0.21 px after native activation. Desktop 1487 × 1058 and narrow 390 × 844 screenshots are saved under `.analysis/navigation-0.12.0/`. See [release audit](release-audit-0.12.0.md) and `design-qa.md` for scope and limitations.

---

# Validation — 0.11.2 thinking and empty source records

## Live Claude capture — October 15, 2026

Claude Code 2.1.295, reporting `claude-sonnet-5-5`, completed two real requests on a controlled local TTLCache coding example. The example task and starting files were prepared locally; every assistant record and usage value came from the installed authenticated Claude host. The copied native session is byte-identical to its original. Evidence, exact launcher arguments, both host streams, the initial and final files, and verification receipts are retained under `.analysis/native-sessions/thinking-0.11.2/`.

The first print-mode run used `alwaysThinkingEnabled: true`, `showThinkingSummaries: true`, and high effort. It reported 686 thinking tokens inside 3,896 output tokens but retained empty thinking text. A follow-up in the same session explicitly passed the installed host's `--thinking enabled --thinking-display summarized` options. It captured an 817-character thinking summary. The associated response reports 14,692 input tokens (2 uncached, 2,465 cache write, 12,225 cache read), 1,284 output tokens, and 389 thinking tokens included in output. Two native records share that response; the analyzer counts it once. The readable summary is provider-returned text, not the complete internal reasoning or a basis for reconstructing billed token counts; see [Anthropic's display/accounting definitions](https://platform.claude.com/docs/en/build-with-claude/thinking#summarized-thinking).

Independent reconciliation groups the 18 native assistant records into seven provider response identities. Native usage, the sum of the two per-run host usage objects, and the report agree: 69,698 input (14 uncached, 11,476 write, 58,208 read), 5,526 output including 1,075 thinking. Exported masked thinking matches the captured text and its hash. No findings, recommendations, or prose were synthesized, and no separate contextual analyzer investigation was run. The report therefore correctly says **Investigation not run**. The version-specific capture-gap notice remains; this run exercises the observed 2.1.295 shapes, not every possible record shape.

Browser verification opened turn 2's thinking record, expanded the source inspector, enabled wrapping, and opened all response usage fields. A screenshot retains the real text alongside its counts. The Copy control reported success, but Browser Use's virtual clipboard returned no data; exact browser clipboard transfer was not established in this run. The seven existing source-content regressions passed. Claude's own test commands were denied because its command form exceeded the configured allowlist; that history and Claude's qualification remain untouched. A separate local execution of the final 13-test suite passed. That independent check is not attributed to Claude or inserted into its log.

## Release checks

The final full suite passed **227 tests in 23.630 s** with both supplied private corpora enabled. Seven new regressions distinguish retained/empty/missing/redacted/unsupported content, test nested policy omissions and local source opt-in, preserve old text projections, reject empty and whitespace-only claim support, and verify deduplicated response usage including unusable thinking counts. The final focused source/trajectory/presentation/review suite passed 44 tests. JavaScript syntax and native plugin validation are recorded in `.analysis/audit-0.11.2/`.

The exact supplied record at 17:46:43.870000 UTC contains `thinking: ""`. The UI now identifies it as a thinking record, states that no readable thinking text was recorded, and displays zero code panels, line gutters or visible Copy/Wrap controls. Timestamp, source identity and usage links remain. The reconciled response reports 359 inclusive output tokens across two records and no separate thinking count. Its input total remains 204,188 (2 uncached, 322 cache write, 203,864 cache read). No block-level allocation was inferred.

Browser checks covered the actual record, adjacent tool input/result controls, nine labelled synthetic format boundaries, exact masked retained-thinking copy, wrapping, exports without source text, and collapse/reopen. At 390 pixels the reopened source inspector had modal semantics, full width, no outer horizontal overflow and no empty panels. The narrow screenshot API failed; this is a DOM/layout check, not a saved narrow visual check. A desktop screenshot is retained. One background clipboard read returned the previous clipboard value despite the success notice; native browser activation confirmed exact fixture content. Mouse dispatch also timed out on some later background actions; keyboard activation completed those checks.

Regenerated migration and native CSV reports use actual retained investigations. All compared Claude-authored fields remain equal, and the migration's existing source text/hashes/timestamps and metric values are unchanged. No fresh Claude investigation was run for this change; empty-evidence rejection is exercised through the actual engine API. These tests do not establish new model reasoning quality or superiority over `/insights`.

---

# Validation — 0.11.1 source inspector controls

All 18 relevant presentation, library and packaging tests passed (1.959 s), and the renderer JavaScript syntax check passed. The unchanged saved migration and CSV JSON exports were rendered with the updated source controls; embedded report data equals each original export. Browser checks exercised expansion to full width, restoration to docked width, collapse/reopen, retained record/wrapping/inspector scroll, exact input copy, Escape, focus cycling, adjacent source navigation and return to the originating finding. At 390 pixels the inspector filled the viewport, hid the redundant expand control, and collapsed without outer horizontal overflow. Screenshots and receipts are under `.analysis/audit-0.11.1/`. No Claude run or model-quality claim accompanies this presentation change.

During testing, the automation locator scrolled the document before activating the sticky reopen button. Native browser activation preserved the selected report anchor within one pixel (351.48 versus 351.70 px). An early copy check read the clipboard before the async copy finished; waiting for the actual success status confirmed the exact retained command. These are recorded to distinguish test-driver effects from product behavior.

---

# Validation — 0.10.4

205 backend tests passed in 21.519 s with both supplied corpora enabled, including a real subprocess regression for inherited stdin. Fresh Claude investigation and independent review completed on the guided source-explanation fixture and on a native synthetic coding session using the default question. Read the [0.10.4 release audit](release-audit-0.10.4.md) for exact run costs, rejected attempts, authoring checks, browser observations and limitations. The authentication failures below remain historical evidence; sign-in is no longer the blocker.

The native project's final six tests also pass on independent execution. Mechanical checks do not establish semantic correctness: the [usefulness audit](developer-usefulness-audit-2026-10-15.md) records inconsistent completion scope, avoidable repetition and SDK-origin request coverage. Actual saved Claude prose was not edited.

---

# Validation — 0.10.3 release audit

The [release audit](release-audit-0.10.3.md) records the current checks, corrections and limitations. First full pass: 202 tests in 21.747 s. Second full pass: 204 tests in 21.046 s, including both supplied private corpora, archive extraction outside the checkout and terminal authentication failure handling. After the second browser audit found missing linked context on requirement/recovery citations, the final full pass passed 204 tests in 21.892 s. The source/command copy and review-reason behavior is covered by presentation tests and browser interaction checks.

The installed Claude 2.1.295 plugin validator passed with `--strict`. A clean ZIP extraction starts MCP under Python `-I` from a path containing spaces with content disclosure off. An actual Claude host loaded five plugin skills and connected MCP, but its first model call failed expired OAuth. Preserve that as a failed live attempt, not a successful investigation. The new fail-fast path has a mechanical regression; a fresh live citation-quality test awaits operator sign-in.

Browser evidence is under `.analysis/audit-0.10.3/`; [design QA](../design-qa.md) records screenshots and intentional design differences. Prior model outputs were rerendered unchanged. The supplied-log JSON is byte-identical to its prior saved report. The new renderer adds no findings or recommendations.

---

# Validation — 0.10.2 local diagnostic extensions, October 14, 2026

## Implemented and mechanically checked

The final full suite passed **197 tests in 20.594 seconds** with both optional private corpora enabled. New adversarial cases cover a narrower passing retry, changed-command same-goal recovery, a passed check before a later edit, unsupported execution claims, response-content delivery, preserved/merged/withdrawn intent, overlapping episode unions, expected failure and correct denial, cache drops without recorded compaction, matched ratio populations, exact boundary duration, output-byte disclosure, current versus historical instruction evidence, and missing/shared child attribution. Existing collection, source rereading, review, proposal, accounting and renderer tests remain enabled. These are structural and calculation checks, not a claim of semantic accuracy on arbitrary sessions.

The new resource APIs initially repeated large identity populations in every page. The bounded-retrieval check found this before release. Version 0.10.1 replaces that repetition with counts, stable population IDs and five-identity previews; full identities remain available through paging and saved selections. Exact repeated-input/result groups are stored once and paged by member, avoiding quadratic repetition. Default pages on the supplied log were about 25.9 KB for context and 12.8 KB for captured outputs. This is a local payload-size observation, not a model-latency benchmark.

One new response-delivery test initially failed because its test helper referenced events absent from its two-record fixture. The helper setup was corrected and the final full suite passed. The substantive gate still rejects unsupported execution completion, uncited/wrong-role text and text used in place of required verification.

JavaScript syntax and the installed Claude plugin manifest validator passed. The manifest produced only advice about a future marketplace install line; no marketplace is configured. Isolated extraction launched through Python `-I`, completed the MCP handshake, exposed 48 tools and kept content disclosure off by default. The packaged CLI exposes the local artifact manifest. Final runtime, skill and asset bytes match the immutable 0.10.2 live-test ZIP; only documentation changed afterward. The distributable excludes private logs, stores, previews, fixtures and the Jev variant. An initial release probe omitted MCP's initialized notification and was correctly rejected; the corrected handshake passed. Package fingerprints and source equality are recorded in `.analysis/release-verification-0.10.2.json`.

## Observed approved-Claude development behavior

All runs used the installed approved host, which reported `claude-sonnet-5-5`, controlled excerpts, immutable plugin snapshots, a separate review host and unchanged saved Claude prose. These are guided, explicitly synthetic integration exercises, not held-out cases or a comparison with `/insights`.

| Run directory under `.analysis/claude-examples/` | Actual saved behavior | Host-reported resources and audit |
| --- | --- | --- |
| `synthetic-evidence-0.10.0` | Completed declared inquiry; 2 active incidents, 6 requirements, 2 unverified, no recommendation. Distinguished two-case retry from three-case r1 pass; kept r2 unverified after another edit and a child launch without its result. Historical v1 already required final verification; current v2 did not establish historical behavior. Policy denial was preserved as successful enforcement. No recovery episode was saved. | 408.98 s, $1.9916462. Exact authored output, standard HTML, canonical accounting and executed-tool policy passed. Strict `allowed_calls_only` remained **false** because both hosts attempted a nonexistent placeholder reader; the host rejected both before execution. |
| `synthetic-recovery-0.10.1` | Completed declared inquiry; 1 expected/recovered incident with a three-attempt episode, 5 requirements, 2 unverified, no recommendation. Claude justified changed-command recovery with an explicit same-fixture result caveat and used the episode union and all three new pair/boundary formulas. | 207.40 s, $1.2464092; 41 tool calls. All origin, exact-output, standard HTML, canonical and permitted-tool audits passed. |
| `synthetic-response-0.10.2` | Completed declared inquiry; 1 incident, 2 requirements, no recommendation. The requested one-sentence explanation was supported as delivered text. A later “Tests passed” assertion remained unverified because no call/result was captured. | 94.17 s, $0.6272; 22 tool calls. All origin, exact-output, standard HTML, canonical and permitted-tool audits passed; no rejected tool submissions. |

The first run's two maps and three incident versions remain intact. Its rejected invalid check identities and negative review checks are retained. It correctly separates an immediate final-revision check from a persistent plugin change, but that observed example does not prove the model always does so. No actual saved recommendation was generated in these runs; existing readiness/copy checks still use separate mechanical fixtures.

The recovery run selected 3 responses and 3 tools: 11,620 input tokens (220 uncached, 420 cache creation, 10,980 cache read), 160 output tokens and 1,450 ms of explicit execution durations. Its selected timestamp interval was separately 5 seconds, including any intervening work. The registered before/after measurements returned −1,380 input tokens, −13.333333333333341 cache-read percentage points and 80 ms recorded compaction duration. The earlier 10,000-to-1,500 input drop had no recorded compaction and was not labelled one. Those fixture values demonstrate accounting, not real workload cost or benefit.

The recovery host retried invalid JSON and invalid evidence submissions. It left an explanation requirement unverified partly because the initial policy demanded a tool/artifact result for every completed requirement. That exposed an overstrict mechanical rule. Version 0.10.2 adds an explicit requested-response-content path, with retained assistant text, inspected references and a stated basis; it cannot override required execution verification. Earlier Claude outputs were not edited or relabelled.

The 0.10.2 live run exercised this distinction successfully and its independent reviewer retained it. Claude used `delivered_response_evidence` for the explanatory sentence and cited the actual response. It did not use that exception for the unsupported test-pass statement. This observed result covers one guided fixture; semantic scope and truth still require contextual judgment.

## Presentation and remaining evidence

The latest renderer preserves the corrected document design. Browser checks exercised requirement-to-revision source links, stale/narrow check flags, fault attribution and separate immediate/persistent actions, recovery resources, recorded-compaction navigation, all token categories, resource paging and HTML round-trip. The supplied-log report retains all authored 0.8.1 content; only deterministic resource views and presentation are new. It has no new model-authored map or episode. Exact report/export checks and screenshots are recorded in `design-qa.md` and the local release audit.

No Ally compatibility is established. Before implementing retrieval, obtain representative versioned parent/child exports and linkage, task-specific artifact/revision IDs, historically loaded component/instruction snapshots with scope/precedence, disclosure policy, and the actual authentication/endpoint/deployment contract plus test access. Jira/PR/CI access must answer a material session-specific evidence gap. Active-time decomposition, concurrency savings and critical paths remain deferred without starts, ends and dependencies. The workload paper informs background only; it supplies no quality thresholds or waste scores.

Independent diagnosis labels, held-out requirement completeness, developer usefulness and the specified `/insights` comparison are still absent. No superiority, slop-free, causal-benefit or speed claim follows from these tests.

---

# Validation — 0.9.0 presentation and 0.8.1 managed rerun, October 14, 2026

The 0.8.1 supplied-log run completed its declared task-outcome investigation after separate investigation and review hosts. It read all 32 main requests, saved 2 active incidents, 6 active failure explanations and no recommendations. Host-reported total: 539.55 seconds, $2.7285028, 69 tool calls. Exact authored-record, permitted-tool, canonical-accounting and standard-HTML audits passed. No topic anchors were supplied and no Claude text was edited.

The shell explanation now identifies the unquoted variable's unsplit path list without inventing a proven shell setting. It qualifies recovery because the retry includes only 9 of 11 original units and the result read was partial. The independent reviewer located later evidence resolving the breakpoint and icon lookups and connected the final OOM output to the background task and killed rerun. All superseded versions and review checks remain saved.

Completed status describes the declared inquiry, not developer-task completion or exhaustive trajectory review. Mid-session assistant work was sampled; the omitted jq units were not followed to the end. The second crashed suite's identity, rerun result and 16 child traces remain unavailable or unverified. This development case is not held-out evidence of superiority.

The 0.9.0 renderer uses the final 0.8.1 JSON unchanged. It adds the corrected document layout, a responsive paired input/result inspector, full saved-source copying, source context, exact five-category token breakdowns and separate analyzer usage. The fixture, browser, export and visual checks are recorded in the latest section of design-qa.md. Runtime, skills and tested 0.8.1 ZIP are preserved; this presentation does not rerun or rewrite the investigation.

---

# Validation — 0.8.1 development, October 14, 2026

The first independent-review run, `supplied-session-0.8.0-reviewed`, is preserved unchanged. Both Claude hosts completed their calls, but Claude finalized the investigation as partial by choice. It used $2.3566788 of its $4 host-reported allocation and 507.25 seconds of its 720-second limit. It corrected the shell explanation, found the later breakpoints type declaration, read the original Jest OOM result and qualified the nine-of-eleven-directory retry. It still had not mapped most main-user requests, so the no-action conclusion remained explicitly narrow. That run is not relabelled complete.

All saved authored fields, review checks, draft history and standard HTML matched submitted data; canonical accounting was unchanged. The old aggregate transport audit was false because Claude attempted one nonexistent placeholder tool, which the host rejected before execution. The attempt, malformed input retries and failed quote checks are retained in the original transcript. Version 0.8.1 separates that failed attempt check from executed-tool policy; a denial is accepted only for the exact host “No such tool available” error, while missing or other results remain unverified. The failed `allowed_calls_only` flag is never hidden.

The follow-up workflow requires a complete main-request intent map, keeps voluntary partial finish calls as checkpoints, and can start one bounded review continuation with remaining budget. Missing source capture and incomplete investigation remain distinct. Negative checks may be recorded against superseded records; old positive checks cannot approve revisions. Literal quotes may be a short scalar when that is the relevant recorded output. These changes address observed workflow friction; they do not certify Claude's causal reasoning.

The 0.8.0 implementation passed 163 full tests and isolated packaged CLI/MCP checks (44 tools). Later review/timeout regressions are tested before the 0.8.1 run. Its live result will be recorded separately after execution. No Codex prose changes were made.

---

# Validation — 0.7.0, October 14, 2026

The full offline suite passed **151 tests** in 14.078 seconds with both private corpus regressions enabled. Nine new collection/child tests cover single-file and renamed-source collection, nested links, metadata-only links, missing/parent-only cases, unsafe identity and symlink rejection, exclusion of unrelated/unlinked sources, controlled disclosure, paged child access, CLI import, resumed traces and shared response identity accounting. The failure explanation tests cover scoped original evidence, read receipts, later results, chronological recovery, revision history, exact saved wording and cache-stable export serialization.

Two real Claude development runs were retained under `.analysis/claude-examples/`:

- `supplied-session-0.6.0-failure-explanations`: partial; six explained attempts, no incidents or recommendations. Claude skipped available retry results. Exact submitted wording passed, but HTML byte comparison failed because an initially populated source projection cache changed object-key order on the next export.
- `supplied-session-0.6.0-follow-up-check`: partial; six active explanations, one earlier explanation revision retained, one incident, zero recommendations. All submitted-output, allowed-tool, unchanged canonical analysis and standard-renderer checks passed. The next-call discovery pointers and stronger follow-up prerequisites led Claude to read later results. Claude revised one recovery label from recovered to unknown after an empty search result. The run remains partial; this is not a complete session investigation or a diagnostic accuracy score.

The cache-order bug was fixed by deterministic serialization and reproduced in a regression test. The earlier failed audit was not modified. All active and superseded explanations remain saved. No Codex prose pass was applied.

A manual source check found a remaining factual problem in the later run: the turn-13 explanation says the shell variable was quoted, but the loop uses unquoted `$UNITS`. The observed single-path failure is recorded, but that causal wording is inaccurate. The explanation and its evidence remain unchanged. The overall synopsis and incident also overgeneralize the attempts as corrected, while the breakpoints information remains unconfirmed. These are model-quality limits, not renderer defects, and must not be hidden by polishing the report. An inspected reference or later successful command does not prove entailment or that the original information need was met.

The packaged 0.7.0 Claude integration run, `subagents-0.7.0`, explicitly used `get_subagent_details` for the parent, nested and unavailable invocations. Its read receipts cover six main records, nine child-a records and all three child-b records. It saved one child-failure explanation, one incident and zero recommendations, with partial status because the fixture intentionally lacks one child trace. The host reported 68.64 seconds and $0.4577072. Exact submitted-output, allowed-tool, canonical-accounting and standard-renderer audits passed. This was a guided synthetic integration check, not a held-out diagnosis evaluation. The final ZIP retains identical runtime/skill bytes; documentation records this result afterward.

A final focused run of 47 failure, child and diagnostic tests passed after the last small import validation/navigation changes. Browser checks covered actual missing child traces, child source access/back navigation, nested invocations, 20-to-35-record pagination, child failures, a 390-pixel viewport without document/dialog overflow, and export/reopen without duplicate records. Exported payload equality, manifest validation, JavaScript syntax and isolated final-package checks are recorded in the release audit.

The supplied log has no captured child traces. Available-child behavior is tested using explicitly synthetic native-layout fixtures, including a 35-record child with a nested child, one unavailable child, and an excluded unlinked child. The actual report is rendered from the saved Claude investigation with its authored fields compared for equality. Final browser and package checks are recorded in `design-qa.md` and the private release audit. No Ally service deployment or backend API integration is claimed.

---

# Validation — 0.5.1, October 14, 2026

65 scoped workflow/diagnostic tests passed in 8.721 seconds; JavaScript syntax validation passed. The new regression checks that failure details use the same requested-invocation/outcome predicate as the count, preserve repeated attempts, exclude other patterns, rejections, unknown and unrequested outcomes, respect metadata-only disclosure and leave zero counts unlinked.

The actual saved report has two nonzero pattern counts, each containing three invocations. Browser checks opened both groups and followed their original result, tool input, back-to-failures and turn-context links. The renderer uses literal previews and leaves all saved model output and the report JSON payload unchanged. This is a reporting-only update; Claude was not rerun. The original 0.5.0 ZIP and live-run outputs are retained. Release checks and preview fingerprints are in `.analysis/release-verification-0.5.1.json`.

---

# Validation history — 0.5.0, October 14, 2026

Environment: macOS, Python 3.9.6/SQLite, installed authenticated Claude Code 2.1.295. The live host reported `claude-sonnet-5-5` for the requested `sonnet` alias. All model output remains unchanged. The checks below distinguish implementation behavior from diagnostic quality.

## Mechanical and report checks

All **131 tests passed** in 12.543 seconds with both optional private-corpus regressions enabled. The 27 new cases cover v2 inquiry closure, primary-result and inspected-range requirements, claim ownership, exact edits and file growth, stale and incomplete instruction inventories, duplicate requirements, existing skill invocations, ambiguous anchors, creation at an admitted existing path, preserved empty deletion text, literal coverage-count discrepancies, source disclosure and unchanged authored output. The legacy v1 workflow remains covered under its original policy.

The plugin manifest validator passed without errors or warnings. The final ZIP is checked separately from the earlier live-run snapshots: isolated Python `-I` launch, MCP initialization, tool inventory, default disclosure, package/source equality and excluded private files are recorded in `.analysis/release-verification-0.5.0.json`. Those mechanical checks do not imply that the final package received a new live Claude evaluation after the last count-check change.

The report was inspected in the in-app browser with actual saved output and separate, clearly labelled synthetic fixtures. Checks include long requests with complete source text, multiple findings linking to one proposal, exact replacement and invocation copying, zero recommendations, unknown usage, incomplete and not-run investigations, expandable turn patterns, evidence navigation, HTML/JSON export and narrow layouts. Cached input remains included in the input total; observed spans remain distinct from active time. Detailed visual evidence is in the local `design-qa.md` and private preview directory.

## Every 0.5.0 Claude development run

All runs used the approved host and controlled excerpts. All authored findings, proposals, synopsis text, inquiry records and host responses were retained. These are development cases, not held-out evidence of superiority.

| Local run directory | Saved investigation | Audit and material limits | Findings / proposals |
| --- | --- | --- | --- |
| `.analysis/investigation-smoke/session-v05-xg9h184c/run` | Completed; no action | Exact output and allowed tools passed; requested failing-test recovery fixture | 1 / 0 |
| `.analysis/investigation-smoke/session-v05-sh2_ozlu/run` | Completed; findings | Exact output and allowed tools passed; successful exit contradicted by original syntax-error result | 1 / 0 |
| `.analysis/investigation-smoke/session-v05-gnvenhcu/run` | Completed; findings | Strict tool audit failed: attempted nonexistent placeholder reader before using the correct reader; later text was retrieved | 1 / 0 |
| `.analysis/claude-examples/supplied-session-0.5.0-packaged` | Partial; insufficient evidence | Authored-output and allowed-tool checks passed; HTML comparison failed because renderer assets changed during the live run | 1 / 0 |
| `.analysis/claude-examples/supplied-session-0.5.0-release-check` | Partial; findings | Exact output, allowed tools and HTML comparison passed; available middle sections remained unread by model choice | 1 / 0 |

The first supplied-session run reported 62.45 seconds and $0.4369742; the release check reported 64.82 seconds and $0.4575286. Neither reached the $3 budget or 360-second timeout. Both inspected the original failing test result, improving on the earlier narrative-only investigation. Both still stopped early. The release check kept the cause provisional and saved no proposal; it did not establish that the entire migration was verified. A successful host call is not a completed investigation.

The asset comparison failure led to a fix: the renderer now loads its CSS and JavaScript together at import time, rather than rereading changing assets during export. A regression test covers this. The original failed audit and HTML remain unchanged. The later release-check export passed the exact renderer audit.

The release-check synopsis said **17** child traces were missing; the captured scope has **16 distinct child identities** without traces. A subsequent narrow deterministic check flags recognized literal missing-child counts and blocks completed status until a mismatch is resolved. It does not edit the sentence or claim to validate arbitrary quantities, quoted context or semantic scope. The final report was rendered from the same frozen saved run, with all authored fields compared for equality; the original HTML remains unchanged. The additional warning and render hashes are recorded in `.analysis/report-render-audit-0.5.0.json`. This new check and the explicit overview count were added after the live release check, and have mechanical coverage but no further live Claude run.

## Remaining product-quality work

The shipped workflow now requires a referenced one-to-three-sentence synopsis, separates observed results from participant claims, exposes original inputs/results together, and retains unresolved material questions. These are useful prerequisites, not a guarantee of comprehension, complete investigation or accurate advice. The latest large-source result is still partial and contains a flagged factual error. No outside editor corrected it, and no recommendation was invented to fill the report.

The next quality evaluation should test available-evidence follow-through, task-summary fidelity and false certainty on independently labelled sessions. Held-out diagnosis accuracy, developer review time, recommendation benefit, native Ally adapters and a matched `/insights` comparison remain unmeasured. There is no slop-free certification or general superiority claim. The PM Mermaid source and links were checked; a separate Mermaid rendering test has not been run.

---

# Validation history — 0.4.0, October 14, 2026

Environment: macOS, Python 3.9.6/SQLite, installed authenticated Claude Code 2.1.295. The live host resolved the requested `sonnet` alias to its reported `claude-sonnet-5-5`; this is captured host metadata, not a hardcoded product dependency.

## Mechanical checks

All **104 tests passed** in 9.652 seconds with both optional private-corpus regressions enabled. The suite includes 37 new single-session tests and the 67 existing tests. Bound MCP and CLI subprocesses agree on metrics and reject legacy scope escapes. Long-source paging, batch continuation, immutable text-version fingerprints, unknown data, turn attribution, duplicate versus genuine retry, missing children, graph cycles, proposal revision, target obsolescence, distinct positive/negative fixtures, alternate syntax-error counterexamples, missing runtimes, exact rendering and transactional migration are covered.

The plugin manifest validator passed. Isolated ZIP extraction launched with Python `-I`, exposed all 36 unbound MCP tools, and included the scoped batch reader. No private source, analysis store, report, test fixture or Jev variant is distributed. New source files remain standard-library-only. Package members and release checks are recorded in the local release audit. The exported real-session report was inspected in the browser, including the pattern table, per-turn metrics, needs-evidence recommendation and zero executed checks.

The Mermaid source and its links were checked; the PM diagram is supplied as editable Mermaid in `session-analyzer-product-design.md`. A separate Mermaid rendering test has not been run.

## All development Claude runs

Every run used controlled excerpts through the approved Claude host, loaded the writing skill and preserved exact output. The following table distinguishes host completion from investigation completion and strict transport checks. These cases informed implementation changes and are not held-out evaluation.

| Local case directory under `.analysis/claude-examples/` | Saved result | Origin/allowed-tool audit | Findings / proposals |
| --- | --- | --- | --- |
| `expected-recovery-0.4.0` | Completed; no action supported | Passed | 1 / 0 |
| `false-success-0.4.0` | Completed; findings | Failed: attempted nonexistent placeholder tool | 1 / 0 |
| `supplied-session-0.4.0` | Partial; insufficient evidence | Passed | 1 / 0 |
| `supplied-session-0.4.0-bounded` | Partial; findings | Failed: attempted nonexistent placeholder tool | 1 / 0 |
| `supplied-session-0.4.0-packaged` | Partial; findings | Passed | 2 / 1 |

In both failed tool audits the host rejected the nonexistent tool; saved text still matched the model's actual submissions. The first large-source run exposed a turn-page size problem. Compact turn pages and paged membership fixed the transport issue. The packaged run used only advertised tools, retained two provisional incidents and a needs-evidence recommendation, and completed its host call successfully; its investigation remained partial.

The packaged run took 80.19 seconds and reported $0.5434636 of analyzer model cost. It did **not** reach the $3 host budget or 360-second timeout. Claude acknowledged not reading raw tool results that were available, including a crash result, and relied on earlier assistant statements for several claims. Its recommendation lacks the target snapshot and contextual review required for readiness. The engine retained it as `needs_evidence`, with zero executed checks. This is a remaining investigation-quality problem, not missing parser access or a model timeout.

No recommendation or summary was rewritten by Codex. All candidates, final prose, host calls, failures and partial states remain in their original run directories. The packaged run also retains the exact tested ZIP. The visible preview is a byte-for-byte copy of its standard HTML export. The earlier 0.3.0 report remains unchanged.

## Guided long-result smoke test

The packaged workflow also ran against a public synthetic result whose final test outcome appears after 18,400 characters. Claude called the bounded reader with the fingerprint and the later offset, found the final success and saved a completed no-action conclusion. It attempted `read_investigation_evidence_placeholder` first; the host rejected that nonexistent tool, so the strict tool-use audit failed despite successful subsequent retrieval. All results remain under `.analysis/investigation-smoke/session-v04-vzn32elt/`.

This was explicitly guided toward the long result and is a retrieval check, not unassisted discovery. The runner's old unconditional unanchored-prompt flag did not distinguish a custom test question; the runner now records custom questions separately and leaves that attestation unknown. The original run audit is retained unchanged, with this limitation documented separately.

## Retrieval measurement

A 1,001-event synthetic session was used for five warm literal-search queries per arm, with three independently specified target events and predeclared budgets. No model participated.

| Path | Median warm search | Relevant-record recall |
| --- | ---: | ---: |
| Legacy projected scan | 22.36 ms | 3/3 |
| Cached flat retrieval | 16.09 ms | 3/3 |
| Same cached search with graph available | 15.86 ms | 3/3 |

Scope/graph build took 89.94 ms and cache population 40.41 ms. One-hop direct indexed lookup took 0.53 ms versus 5.40 ms for general graph retrieval. The first implementation reopened SQLite per source and was slower; that measurement remains in `.analysis/retrieval-benchmark-0.4.0.json`. Connection-reuse results are in `.analysis/retrieval-benchmark-0.4.0-connection-reuse.json`.

These are local warm-query measurements with shared setup, not independent end-to-end arm timings. OS caches were not reset; memory is process-level. The apparent search benefit comes from caching, not graph traversal. A model investigation ablation and developer review-time study remain pending.

## Quality limits

The requested metrics, pattern figure and structural investigation contract are implemented. A successful test invocation or origin check does not prove a diagnosis. Live evidence shows continued risk of premature stopping, narrative reliance and unsupported classification. There is no slop-free certification, demonstrated recommendation benefit, or superiority claim over `/insights`. The [evaluation protocol](investigation-evaluation.md) keeps those questions separate from feature verification.

---

# Validation history — October 13, 2026

Environment: macOS 27.0.1, Apple Silicon, Python 3.9.6. Runtime: Python standard library + SQLite. Claude Code host: 2.1.295, supplied by the desktop app and authenticated with the user's subscription.

## Trajectory retrieval — 0.3.0

The current supplied-log example is Claude's unedited output from `scripts/run_claude_investigation.py`. The runner supplied the analysis and a general request for skill/prompt recommendations, with no event or topic anchors. Claude loaded the writing skill, made four trajectory searches and three reread calls alongside other analyzer queries, saved two recommendations and exported the report. All saved recommendation bodies exactly match its tool inputs; the HTML exactly matches the standard renderer. No Codex wording, filtering or selected sentences were substituted. The visible report was refreshed and checked in the browser. The complete transcript, final answer, structured recommendations and origin audit are under `.analysis/claude-examples/supplied-session-0.3.0/`.

The report's SHA-256 is `70e46c96ceff7b24ff326c62c589f8500f906d4aec4f32a0763c44f0665ea81b`. It is an actual workflow result, not a certified quality pass. Its scope and uncertainties are Claude's own output. The earlier Codex-edited example was archived and replaced in the visible preview. An origin check proves agreement with the captured tool calls, not factual accuracy or general superiority over `/insights`.

67 tests passed in the final run (4.156 seconds), including both opt-in private-corpus regressions. Eight new tests verify long Unicode input reconstruction without gaps, literal search past preview limits, empty partial search pages, hit-limit pagination, session/agent isolation, adjacent-event navigation, masking and omission notices, policy enforcement, fingerprint mismatch rejection, CLI/MCP agreement and unchanged source/canonical data. Local retrieval also ran with socket creation blocked. The investigation skill and Claude plugin validators passed.

The actual Claude host loaded the writing skill and used both new MCP tools on synthetic data. It searched the long check result, then read from character 17,500 and received the final outcome beyond the old preview. The test checks returned tool content as well as invocation, and canonical analysis stayed unchanged. No private source was used in this host test. Reproduce with `scripts/test_claude_investigation.py --reread`. The successful source-host record is `.analysis/investigation-smoke/run-mykp68tw/result.json`.

This passed the retrieval/transport checks, not a semantic-quality assessment. The model still described R06 as overstating failure despite the rule's stated exact-retry scope, and suggested a fallback without establishing equivalent check coverage. These remain examples of why source access and a writing skill do not certify an interpretation. An earlier host run retrieved the correct tail too, but the old test harness incorrectly required use of the preview tool; the harness now accepts a successful controlled reread and verifies its content.

Local verification on the supplied log reread the document-writing event at source line 566 in three pages: 0–6,000, 6,000–12,000 and 12,000–15,216 characters in the masked text view. Concatenating those pages exactly matched that view without changing source records or canonical results. A four-page local search covered all 3,569 retained events and located the failed source-size selection at line 575. The audit is `.analysis/ally-writing/trajectory-source-verification.json`; it stores references and lengths, not transcript text. These are retrieval checks, not a large-corpus performance or model-cost benchmark.

The final 0.3.0 ZIP contains 26 allowlisted files (71,644 bytes; SHA-256 `48ee4145421421b88d4e7661a15a49b06f822ca438bff5c45f406f2a46b77aaf`). Every member matches its source. Isolated extraction and Python `-I` launch exposed all 23 MCP tools with content disclosure disabled by default. Private sources, stores, examples, development tests and the Jev variant are excluded. Verification is recorded in `.analysis/ally-writing/verification-0.3.0.json`.

## Writing addition — 0.2.1

The shared `write-report` skill and revised `investigate` skill passed frontmatter validation. The Claude plugin validator passed. The live synthetic host test successfully invoked the writing skill, used the analyzer MCP tools, saved a recommendation and exported a report without changing canonical analysis. This is a transport and invocation check, not a claim that every sentence passed evidence review.

With the user's approval for Claude and controlled excerpts, a targeted demonstration used the supplied `session.log`. All 3,569 records in its one session were parsed locally. The revised live run made five excerpt calls: 15,183 excerpt characters (15,249 UTF-8 bytes, including repeats), covering text from 31 distinct events. All analyzer tool-result contents together measured 75,149 UTF-8 bytes. The original source is 7,487,471 bytes. These figures exclude skill/tool definitions, prompts, outputs and repeated context or cache processing; they are not token or cost savings. Topic anchors were selected locally, so this was not an unassisted discovery benchmark.

Both model drafts required editing. Problems included reusing an unverified transcript count as a comparison baseline, stopping before later recovery, misstating the number of excerpt calls, and proposing an incoherent follow-up measure. The writing skill was tightened after the first draft. The second draft still needed review; a skill alone does not eliminate low-quality output. The synthetic follow-up also retained imprecise recovery wording and an unsuitable expectation that a rule flag would disappear. Those outputs are not marked as having passed a semantic-quality evaluation.

An earlier local example was edited by Codex against the cited events. That example is superseded: the user correctly required the demonstration to show Claude's production output without outside editing. The edited example is not evidence of the workflow's quality. Its raw drafts, edited records and historical review audit remain separately available under `.analysis/ally-writing/`; none are packaged. Current examples use the unedited-output runner and keep any evaluator assessment separate.

The 0.2.1 package has 25 allowlisted files, including all four skills and the writing-quality reference. An isolated extraction launched successfully with Python `-I` and exposed the same 21 MCP tools. Private logs, stores, tests and the Jev variant are excluded. The rendered example was inspected in the in-app browser. The Python regression suite includes HTML escaping and canonical-result invariance; its final run is recorded with the local audit.

## Investigation extension — 0.2.0

59 tests passed in 3.622 seconds with both opt-in private-corpus regressions enabled. The 11 new tests cover same-agent context, subsequent recovery through changed commands, dataset isolation, operator disclosure, total/per-event excerpt bounds, masking and omitted fields, nested payload validation, invented references and metric mismatches, idempotency, append-only review history, escaped HTML, CLI/MCP equality and canonical-result invariance. The new local operations were also exercised with socket creation blocked.

The skill frontmatter validator and actual Claude plugin validator passed. Source-host testing invoked `/ally-session-analyzer:investigate` against public synthetic data with controlled excerpt access. Claude connected to the MCP server, discovered the new skill, read before/after context, saved a reference-checked recommendation and completed an investigation report export. No private source logs were sent. Canonical analysis stayed byte-identical during the investigation.

The initial live run made an unsupported qualitative cost inference from small result sizes. The skill was revised to forbid that inference and to scope retry advice to the actual error condition rather than a generic exit code. The second run retained unknown cost, recognized a changed-command recovery, kept the child failure separate and treated requested polling as intentional. This is a narrow behavioral check, not evidence of general diagnostic accuracy; the saved prose remains unreviewed. In particular, a successful fallback should not be promoted into independently verified whole-task completion.

Reproduce with `scripts/test_claude_investigation.py`. The revised source-host result is in `.analysis/investigation-smoke/run-d_w1qa0j/result.json`. Its exported HTML was opened over localhost and the evidence/checked-metric disclosure was expanded successfully. The report makes no remote requests and contains no scripts. The temporary preview server is not required to use the exported HTML.

No head-to-head comparison against `/insights` has been run. Use [the evaluation protocol](investigation-evaluation.md) before making that claim. The historical 0.1 validation below records the unchanged accounting foundation.

The 0.2.0 ZIP contains 23 allowlisted files. Every archive member matched its source bytes; no tests, logs, private stores or Jev variant files were included. Extracting into an isolated temporary directory and launching with Python `-I` discovered all 21 MCP tools with content disclosure off by default. Package and verification metadata are retained locally in `.analysis/investigation-smoke/verification.json`.

## Automated tests

48 tests passed in 3.752 seconds, including both opt-in private-corpus regressions. The sources are not committed or included in the plugin ZIP.

```sh
ALLY_TEST_SESSION="/absolute/path/session.log" \
ALLY_TEST_ARCHIVE="/absolute/path/claude session log example.zip" \
python3 -m unittest discover -v
```

Coverage includes repeated usage blocks, supported provisional updates, conflicting/unknown updates, interrupted responses, thinking/output relationships, cache TTL pricing, missing metrics, synthetic notices, conflicting event IDs, copied history, tool retries, explicit rejection/validation failures, missing child logs, response/agent scopes, repeated failure and monitoring rules, sequence windows, inverse edits, malformed/oversized lines, ZIP repacking invariance, traversal/symlink rejection, offline core execution with socket creation blocked, report/CSV injection handling, disclosure policy, annotations, CLI/MCP equality, pagination, protocol negotiation, and real stdio subprocess transport.

The supplied Ally file produced the values in [implementation status](implementation-status.md). The earlier example ZIP produced 33 observed session IDs, 3,291 response groups including 5 synthetic groups, 2,597 tool calls/results and 79 error-marked results. Its malformed line is quarantined; one eligible response has unavailable usage, so token totals remain coverage-qualified.

## Actual Claude Code integration

`claude plugin validate .` passed. An authenticated Claude Code CLI then loaded the plugin first from the source directory and then from the distributable ZIP. In both cases:

- The actual Claude MCP client connected to `plugin:ally-session-analyzer:ally-session-analyzer`.
- The host discovered `ally-session-analyzer:analyze` and `ally-session-analyzer:explain`.
- Claude called `get_definitions`, `import_bundle`, `get_job`, `analyze_batch`, `get_job`, `get_summary`, and `get_findings` through the plugin.
- The returned engine metrics matched the public fixture: **5 model responses, 4 tool calls, 210 output tokens, 58 thinking tokens**, with R01 and R06 findings.
- Both host runs completed with no permission denials. No private session source was sent to Claude for this test. The packaged test reused the identical imported fixture snapshot and computed a new analysis after the adapter revision.

Reproduce using `scripts/test_claude_plugin.py`; add `--plugin dist/ally-session-analyzer-0.1.0.zip` to test the archive. The last structured result and host transcript are retained locally in `.analysis/claude-smoke/`. Test assertions inspect tool-returned metrics, not only the model's final prose.

This validates the current CLI host's loader and MCP path. Permanent desktop installation, other host versions and other operating systems are not certified by that result.

## Report interaction

The generated Ally report was opened in a browser and exercised for session filtering, an empty search, session selection, activity/type/outcome filtering, source-line evidence dialogs, and the coverage/definition view. Observed values matched the engine, and browser error logs were empty. The final report displays the refined breakdown of 4 user rejections, 5 validation failures and 6 execution failures. Its evidence command includes the actual local store path, separately from canonical JSON.

HTML, detailed JSON and session CSV artifacts are in `.analysis/reports/`. A preview image is saved there. Reports contain source-derived metadata and hashes; they exclude raw transcript content.

## Scale measurement

`python3 scripts/benchmark.py --sessions 500 --steps 50`

| Measurement | Result |
|---|---:|
| Synthetic sessions | 500 |
| Raw records | 50,000 |
| Model responses / tool calls | 25,000 / 25,000 |
| Expanded input | 33,140,000 bytes |
| Import | 1.714 s |
| Analysis | 22.240 s |
| Full batch metrics query | 0.744 s |
| Peak process RSS | 408,961,024 bytes (~390 MiB) |

Expected counts and output totals were asserted. This is one measurement with short synthetic records, not a 2 GiB real-session benchmark, a hardware-independent guarantee, or a loop precision study. The proposed capacity/latency target in the draft spec remains unproven for representative maximum-size input.

The release ZIP contains 19 allowlisted implementation/documentation files and excludes private logs, databases, reports, credentials and unrelated variants. Archive hash and size are printed by the deterministic package builder.


## 0.11.0 — directory library and semantic consistency

All 220 backend tests passed with both supplied corpora enabled; targeted library/export and isolated packaging checks passed after the embedded-download fix. Browser checks covered native local sessions and a 65-log synthetic directory, exact source copy, source navigation, turn expansion, filtering, paging, keyboard selection, saved versions, explicit Claude launch and measured 390×844 layouts. HTML and JSON downloads matched saved bytes.

Three actual approved-Claude runs completed with unchanged output: two native CSV investigations (35/$1.6454725999999997 and 40/$1.7117254000000002 calls/host-reported dollars) and the new cleanup regression (44/$1.8955403999999998). All saved zero recommendations and passed provenance/transport checks. SDK requests are now investigated as task requests; human origin remains distinct. The cleanup run separated missed preparation from passing partial checks and remaining verification. The final CSV run corrected the benign-versus-expected classification.

Interpretation quality is not certified: the two CSV runs disagree about a reading-order requirement, and repetition remains in the prose. The new synthetic fixture is not independently held-out evidence. See [release audit](release-audit-0.11.0.md) for rejected candidates, exact artifacts and remaining limitations. No authored output was manually improved.
