# 0.16.1 — managed review repair and timeline headings

October 16, 2026. Claude-authored investigation output and prior revisions remain unedited.

## Confirmed workflow defect

The previous migration review's two rejected requirement-map submissions had 46 and 45 source references respectively, with **zero missing citation explanations**. Each also supplied one relevant change event ID. The ordering validator constructed an internal identity-only reference for that ID and incorrectly applied the reader-facing caption policy to it. Claude could not add an explanation to that string-only field. The same path affected recovery-attempt event membership. The earlier explanation attributing those rejections to missing Claude captions was incomplete; this reproduction establishes an analyzer defect.

Internal ordering/membership anchors now keep scope and evidence-read checks without requiring captions. Actual reader-facing references still require Claude-authored explanations. Both original rejected maps' verification inputs pass the repaired read-only check; no historical output was edited or resaved. Synthetic regressions cover unread and foreign anchors, genuine same-goal recovery, unchanged saved payloads, and the requirement-map path.

Managed MCP schemas now advertise their existing nested citation and semantic-check requirements. Missing-field errors identify the path and fields; semantic errors identify the record and required aspects. Review instructions save substantive checks incrementally, repair rejected saves and refresh revision dependencies. The runner reserves half the initial money/time allowance for review and includes each actual stage allowance in its saved prompt. Checks still reject unsupported claims, stale reviews and missing evidence.

## Mechanical and browser checks

- Full suite: 306 discovered, 304 passed, two optional private-corpus tests skipped (27.461 seconds).
- After the presentation change: 39 report/evidence/packaging checks passed.
- A further 18 review-workflow checks passed after guarding the transport auditor against host-retained malformed tool arguments. The synthetic runner case preserves the rejected call without treating it as a saved review check. This guard was added after the live runner started; that run did not encounter malformed review-check arguments.
- Final review-workflow and clean-package checks: 19 passed in 3.886 seconds. The local Claude plugin manifest passed strict validation; the release archive excludes private sources.
- Context/cache tables use a labelled, focusable scroll region. On desktop, all seven headings stayed at the region's top after PageDown. At 390 × 844, the table retained readable column widths and horizontal access: header and row column coordinates remained equal at 402 pixels horizontal scroll and 593 pixels vertical scroll. Loading the next page increased visible rows from 30 to 60.
- The same context renderer serves main, turn and child details; print removes the scroll-height limit. Actual saved migration JSON was unchanged after rendering.
- Screenshots are retained locally under `.analysis/workflow-0.16.1/timeline-desktop.jpg` and `timeline-narrow.jpg`; no private screenshots are packaged.

## Migration rerun

The authorized run uses the same supplied migration log and the same operator-authored question as the previous focused run, with a $12 total cap and 1,800-second timeout. It is a new immutable investigation, not a modification of the earlier report. Its plugin snapshot, prompts, rejected submissions, tool results and Claude revisions are retained under `.analysis/workflow-0.16.1/migration-run/`. The run began after the workflow fixes; the sticky-header presentation change is rendered over saved output separately.

The run completed with an independent review and successful origin/transport checks. Investigation `investigation_7ab4078852034829984218d31e13a9d0` used $6.1830416 of the $12 cap across two successful hosts ($1.7280008 initial, $4.4550408 review), 83 tool calls and 1,327.805 seconds of runner elapsed time. Neither host hit its money/time limit. The initial host invoked the packaged writing skill; the reviewer fetched the same skill through `get_session_guide`. These are analyzer resources, excluded from the migration session's usage.

Claude saved one current finding, six current failure explanations, a revised requirement map and **zero recommendations**. Eleven current record/draft review checks were saved; five are qualified and six supported. All 32 captured main requests were read and referenced in the map. The map has 14 requirements: one supported as completed and 13 unverified. It explicitly remains a **partial inventory**: early implementation results and some assistant answers were not read, while 16 child traces were unavailable. Completed review therefore does not establish whole-task completion or exhaustive investigation of every requirement.

The revised finding distinguishes a scoped post-edit pass (28 suites, 121 tests), a broader run with two failed suites, the one captured Jest worker crash, and a stopped rerun with no captured result. It preserves uncertainty about the second suite and the crash's cause. Claude's review also corrected the lookup account: a successful retry checked nine of eleven original units, so that recovery is only partial. These are attributed Claude judgments, not conclusions authored by Codex.

The live review still made rejected submissions: malformed JSON, unread source ranges, unsupported completion prerequisites, lost requirement identities, source-order issues and superseded review dependencies. Claude corrected them and finalized; the transcript retains the failures. The historical impossible-caption rejection did not recur. Advertised schemas and stronger instructions improved the workflow but did not eliminate model input errors or establish semantic accuracy on unseen sessions.

Every saved incident, map, inquiry, failure explanation, review check, draft and final synopsis matches a captured Claude tool submission. The canonical measurements and the original migration log/older report hashes are unchanged. The exact new JSON was imported into the local library (SHA-256 `f92fbb6cc2496fbc1a26871dd3cf0063c6d54fb7df05579cd5313ce7c8259926`), keeping one visible migration session and its previous immutable analyses internally. The latest renderer shows the completed status and the saved limits without rewriting prose.

The completed report's finding sequence and decisive test-result source opened correctly in the browser. Its timeline headings remained sticky in the library iframe on desktop and at 390 × 844, including 406 pixels horizontal scrolling and 689.5 pixels vertical scrolling. The viewport was restored and the completed overview left open. Additional captures are `completed-report-desktop.jpg`, `completed-timeline-desktop.jpg` and `completed-timeline-narrow.jpg` under the same private validation directory.

No Ally-only compatibility, exhaustive semantic-quality result or superiority over `/insights` is claimed.
