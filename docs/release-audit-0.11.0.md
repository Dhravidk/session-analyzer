# Release audit — 0.11.0

October 15, 2026. This release adds local session browsing and required semantic consistency review. It preserves prior outputs and does not claim superiority over `/insights`.

## Mechanical checks

The final full run passed all 220 tests with both supplied corpora enabled (23.625 s), including two additional expectedness/citation-identity regressions. An earlier 218-test run and separate corpus check also passed. Library/export and isolated-package checks were repeated after the download transport fix. These cover mechanics and fixtures, not semantic accuracy.

New cases exercise local discovery, two-component folder labels and duplicate labels, symlink rejection, no-model previews, immutable versions, source-change detection including child files, imported data rendering, explicit disclosure, subprocess argument/closed-stdin behavior, loopback request boundaries, SDK task populations, empty denominators, required semantic checks, contradiction rejection and stale opening-review dependencies. Qualified status presentation preserves the exact saved data.

## Model observations

Three approved-Claude runs use the default unanchored prompt: two browser-launched investigations of the native synthetic CSV session, plus a newly authored synthetic cleanup session. The first CSV run exposed a benign/expected classification error and led to the explicit expectedness-basis requirement. Every attempt is retained. These are development/regression evidence, not independent held-out evaluation.

## Browser and packaging

The browser was exercised on the actual local `~/.claude/projects` directory and a separate 65-session synthetic navigation directory. Folder labels, search, saved-report selection, local log opening and explicit Claude launch were checked. A measured 390×844 view had no outer horizontal overflow; the session list and report switch without shrinking text. Screenshots and final checks are retained under `.analysis/audit-0.11.0/`.

## Limits

The local library currently launches trace-plus-linked-child investigations. Extra artifact admission uses the existing CLI manifest. Discovery is bounded and source change detection uses file stats. Additional origin types beyond human/user, inferred and SDK need a verified policy. Actual Ally integration, independently labelled unseen sessions and a matched `/insights` comparison remain pending. The semantic reviewer can still miss contradictions or approve weak prose; no slop-free guarantee is made.


### First CSV run and cleanup regression

The first CSV run completed with zero recommendations, 35 tool calls, 456.44032675 s and host-reported cost $1.6454725999999997. Transport checks passed. It reconstructed two SDK task requests and five mapped requirements; it distinguished the earlier three-test pass from the final six-test pass. The review corrected an inaccurate claim that code content was unavailable by reading the Write input. It also found that tests were read later: the actual request did not explicitly impose a before-edit order on that reading. Therefore the earlier allegation of a missed read is not established for this specific log. Do not force a failure label just to agree with a previous assessment.

Remaining quality problems in that saved output: the outcome repeats part of the synopsis chronology; read-back/BOM caveats repeat in several places; a completed BOM obligation carries an exact-codepoint caveat; the reviewer calls the repaired duplicate-anchor edit expected because it is benign. The run is retained unchanged. The last issue caused a workflow refinement: expected now needs inspected intentional-negative-check or policy-enforcement evidence. It is distinct from no-action and recovery.

The new cleanup fixture explicitly requires reading tests before editing. Claude kept that obligation contradicted, filesystem verification unverified, and the constrained handoff completed. It did not treat the four-test unit-only pass as recovery of the six-test goal. It also identified that a `--dry-run` CLI option was not established by a function-only edit. It saved one unresolved incident and zero recommendations, with no claim of plugin fault. It still repeats some filesystem-test chronology across opening fields. This is useful diagnosis with remaining prose defects, not a slop-free demonstration.

The run exposed a mechanical citation issue: the delivered-response validator compared explanatory wording as well as source/range identity. The validator now compares only source identity, fingerprint and range; a regression verifies different contextual explanations for the same range. Earlier rejected calls remain in the host transcripts.


The embedded report's initial Blob export did not produce a download in the in-app browser. The library now routes its embedded export control through registered saved-file endpoints with attachment headers, without changing the saved report. Both JSON and HTML downloaded successfully and matched their saved files byte-for-byte. Standalone export behavior remains unchanged. Source copy matched the exact retained text; next-record navigation and turn expansion worked. The 65-session check exercised the 60-row page boundary, search, keyboard activation and two distinct full paths with the same two-component folder label.

The cleanup run completed in 428.734462208 s, with 44 tool calls and host-reported cost $1.8955403999999998. All origin/transport checks passed and no unapproved or unknown tool attempts executed. Its oracle was saved before inference and never supplied to Claude; because it was authored by the implementer, it remains a synthetic regression, not independent evaluation.


### Final CSV rerun

The final CSV rerun completed with 40 calls, 335.94043495799997 s and host-reported cost $1.7117254000000002. It saved one finding and zero recommendations. The duplicate-anchor Edit is now `unexpected` and `recovered`, without turning it into a persistent change. It retains two SDK task requests and zero explicit human-origin turns. All origin/transport checks passed.

A material uncertainty remains: this run treats the request as requiring tests to be read before editing, whereas the preceding run interpreted the wording as imposing order only on the baseline test command. The source says “Read README.md and the tests. Run python3 -m unittest -v before changing the code …”. The later read is recorded; a mandatory ordering of that read is not explicit in the same way. The final report presents its interpretation too confidently. Both outputs are retained unchanged. Independent review of intended scope/order is still needed; additional structured checks did not eliminate model interpretation errors. Do not call this release slop-free or claim validated superiority.

The final Claude run used the same investigation, review, writing, accounting and report-rendering files as the shipped candidate. Subsequent differences are confined to `session_library.py` and `session_library.js` for saved-file download transport and navigation handling, exercised by backend/browser checks. Exact file comparisons are in `.analysis/audit-0.11.0/live-runs.json`. Documentation changes are not another Claude run.
