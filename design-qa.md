# Latest design QA — 0.12.1 word-wrap controls

final result: passed for the exercised control

October 15, 2026. Compared the supplied straight-arrow and return-arrow references with the implemented source inspector. The two user-supplied icon assets are retained unchanged with provenance. The icon-only control shows “Enable word wrap” when off and “Disable word wrap” when on. A dark rounded tooltip appears on hover and keyboard focus; the existing plum focus ring remains. Tooltip placement stays within the report viewport, including after long text reflows.

The actual saved CSV report was exercised in the in-app browser: a 5,120-pixel unwrapped source line fits a 311-pixel viewport when wrapped. Tab/Enter operation and Escape dismissal were checked. The source panel remains open when Escape dismisses the tooltip. Report prose and exact-copy values are unchanged. Final full captures: `.analysis/wrap-control/wrap-disabled.png` and `wrap-enabled.png`. The clipped captures omit the separately composited tooltip and are not the visual acceptance evidence. Nineteen relevant presentation, source-content and packaging tests pass; JavaScript syntax validation passes. This does not extend the prior cross-browser or assistive-technology coverage.

---

# Design QA — 0.12.0 session navigation

final result: passed for the exercised design and interactions

October 15, 2026. The session-navigation reference was inspected before implementation and compared alongside the final actual-report capture at 1487 × 1058. Reference: `/Users/dk/.codex/generated_images/01a14022-a2da-7961-bf5a-37d5d3e54b56/exec-cbadcd8b-6598-43e7-afeb-d7de611231a5.png`. Final captures: `.analysis/navigation-0.12.0/desktop.png`, `narrow-report.png`, `narrow-drawer.png`, `narrow-source.png` and `desktop-expanded-source.png`.

The single 56-pixel header, 330-pixel grouped sidebar, lavender selection, warm white document, restrained plum controls, outline icons and horizontal report navigation follow the reference. The actual saved title and prose are longer and remain verbatim. Empty Findings and Proposed changes remain truthful; no sample counts or recommendations fill the layout. Existing metrics/requirements/coverage stay in their established disclosures rather than being reimplemented as a second dashboard. A refresh control replaces the mockup's ambiguous ordering glyph because ordering is already recent-first and the control performs an actual rescan.

The real CSV, TTLCache and Angular-to-React reports retain Findings, turn links, failure explanations, requirements, all token categories, timing distinctions, child coverage, exports and source controls. The source inspector can expand, restore and collapse. Exact copying preserves the saved masked text. The final source-opening check retained the clicked control within 0.21 px. A real Claude update completed; a labelled fixture exercised a failed update while keeping the saved report visible. Neither test edited analysis prose.

At 390 × 844 the session list becomes a dismissible drawer, with report inertness, Escape, focus return and readable 16-pixel opening text. The report does not overflow the viewport; horizontal report navigation/table content scroll locally. A full-width source inspector preserves context and copy controls. Final browser checks also cover full paths, long titles, identical titles in distinct folders, search/disclosures, selection/back navigation, one-entry/latest-report behavior and explicit current/incomplete/new/unknown/running/failed states.

Intentional differences are data-driven length, the retained Outcome navigation, truthful no-content sections and the absence of the sample stale notice on a current report. The notice appears only where new evidence is demonstrated. See [release audit](docs/release-audit-0.12.0.md) for validation evidence and scope. Cross-browser/assistive-technology certification, large-library performance and independent diagnostic quality remain unmeasured. No blocking defect remains in the exercised presentation paths.

---

# 0.10.3 command rows, citation context and release audit

Selected reference: ImageGen option 3, `/Users/dk/.codex/generated_images/01a135ee-3076-7591-9aec-f21ad094cbfa/exec-803b6e6c-b8ec-4396-b25c-5ea9463d1ae0.png`. Compared beside the implemented turn-2 state at 1586×992. The filename-first argument, separate command label, pale selected row, exact field copies and original-record disclosure match the chosen composition. Findings remain by explicit user request. Existing compact report typography, token categories, durations and deeper source controls are intentionally retained rather than removed to reproduce the mockup's simplified contents.

Screenshots in `.analysis/audit-0.10.3/`:

- `desktop-command-rows.jpg`: command/argument fields, original source, Findings and retained token detail.
- `desktop-source-explanation.jpg`: real saved report, exact Claude review note, paired source, quote and coverage. The old note is terse; its wording was not edited.
- `mobile-command-rows.jpg`: verified 390×844 viewport; readable wrapped full path and separate copy controls. Findings remain reachable through the explicitly labelled horizontal table scroll.
- `mobile-source-inspector.jpg`: full-width modal source inspector, native-size code, wrap/copy/context controls. Escape returns focus to the originating control.

No decorative assets were added. The file icon uses the same licensed Feather set as the existing controls. Plain unknown-language source stays plain text. All text and source values come from saved output or deterministic routing labels.

Audit corrections: the browser locator's automatic recentering confounded early position measurements; native activation verifies the changed control is retained within 0.16 px. Opening now anchors to the actual triggering control, including browsers that do not focus buttons on pointer activation. JSON export comparison uses deep equality, not key order. A stale clipboard read after locator activation was retained as inconclusive; native replacement and invocation activation copied the complete saved values exactly. Large-result inspection was checked after a fresh DOM observation: 38,200 retained characters, 627 full lines, exact copied value despite gutters/wrapping.

The second pass verified exact requirement/verification/episode/attribution context in source links, recorded compaction values, 30-to-60-of-839 resource paging, child failure return and working controls inside an exported/reopened HTML report. The context renderer does not replace missing Claude explanations with invented prose.

The browser interaction record is `browser-checks.json`; the complete backend, packaging, live-model and rollout limitations are in [release audit](docs/release-audit-0.10.3.md). No new source-specific sentence is invented for an older report. The new Claude field remains a live-behavior validation gap until authentication is restored.

---

# Latest design QA — 0.10.2

final result: passed

October 14, 2026. The corrected f0df49b2 reference and final 1487 × 1060 real-report screenshot were inspected together. The warm document, compact navigation, restrained plum controls, pale adjacent inspector and dark source panels remain. The actual saved title and three-sentence synopsis are longer than the visual example and remain unchanged. New diagnostic details are disclosures within existing report sections.

Verified in the in-app browser:
- Requirements expand into saved status/scope/revision/evidence. The actual synthetic Claude map shows a narrower passing check and a later check that predates r2; the result link opens the r2 Edit input/result beside the report.
- Fault attribution preserves Claude's distinction between an unresolved verification handoff, adequate historical instructions, an unknown child result, immediate next action and no justified persistent change.
- The saved recovery episode expands into original, corrective and verification attempts. Its union usage includes all five token categories, calls/tools, explicit execution-duration sum and separately labelled per-agent intervals. Expected/recovered work retains zero recommendations.
- The timeline shows all response components, only the actual recorded compaction, its before/after values and duration, and source navigation. The earlier unmarked input drop stays a response change. Real-report resource pages show 30 records, then 60 on continuation; exported/reopened HTML resets to 30 of 839 with usable source controls.
- Actual saved response-delivery evidence renders verbatim and remains separate from an unverified execution claim. Its JSON and HTML exports contain exactly the original report payload.
- The real report retains 16 unavailable child traces and no proposals. Full exact main token totals, turn totals, failure explanations and source navigation remain. The captured-child fixture retains separate child metrics/timeline, source/back navigation and nested invocation details.
- At 390 × 844, document width remains 390, requirement content wraps, and source viewing is a full-width accessible dialog. Input wrapping preserves the copied masked command exactly. Escape closes the inspector and returns to the report.
- Long source/full-result access, recommendation replacement/invocation copy, partial/unknown data and incomplete/not-run states retain the previously exercised 0.9 behavior; those source/copy controls and their existing mechanical regressions remain. This extension does not claim a new live recommendation was produced.

Screenshots: `.analysis/previews/v102-desktop.jpg`, `v102-mobile.jpg`, `v102-mobile-source.jpg`. Preview: `http://127.0.0.1:56558/ally-session-0.10.2.html`. Actual Claude synthetic examples: `ally-synthetic-evidence-0.10.2.html`, `ally-synthetic-recovery-0.10.2.html`, `ally-synthetic-response-0.10.2.html` under the same preview directory.

No browser warnings or errors were reported in the exercised real, requirement and response-delivery views. No observed blocking presentation defect remains. Semantic diagnostic quality, independent evaluation, complete accessibility certification and cross-browser coverage are not implied. All earlier run outputs and visual evidence remain intact.

---

# Design QA history — 0.9.0

final result: passed

October 14, 2026. Compared the corrected f0df49b2 reference and final desktop capture together at 1487 × 1060. The earlier reference is superseded. This result covers presentation and exercised interactions, not diagnostic correctness.

The warm document, 54-pixel header, compact navigation, plum controls, subtle selected rows and adjacent pale source inspector match the chosen hierarchy. Official Feather 4.29.1 outline icons are vendored with their MIT license. Dark source panels retain indentation, readable 13-pixel monospace, line gutters and scrolling. Saved content causes a longer opening than the mockup; neither the title nor synopsis/outcome was shortened or edited.

Verified in the in-app browser:
- Real 0.8.1 investigation: unchanged payload/prose, completed inquiry, unfinished task, 16 missing child traces, two findings, no proposals.
- All five token categories, exact totals, partial subtotals and unknowns; main, child, combined and analyzer populations remain separate.
- Paired input/results, shell/JSON highlighting, unknown output as plain text, wrap controls, adjacent navigation and selected-record identity.
- Actual 140-line source: 120-line excerpt expands to all 140 lines; full copied result equals the saved projection including original tabs and line prefixes.
- Failure explanation text, failure-to-source/back navigation, missing-child invocation, captured 35-record child pagination, nested invocation and child token categories.
- Synthetic 5,365-character request is complete in expanded turn/source; multiple findings link to the same saved proposal.
- Exact replacement and invocation copying, including quotes, shell-like text, Unicode and trailing newline; no application control.
- JSON and exported HTML payloads equal their saved input. Reopened HTML rebuilds expanded rows once and source controls remain usable.
- 390 × 844: no document overflow, readable report, full-width source dialog, wrap and Escape/return. Horizontal turn scrolling remains local to the table.
- Separate completed/no-action, insufficient-evidence, incomplete, not-run and partial-token fixtures. No browser errors or warnings in exercised views.

Screenshots: .analysis/previews/v09-desktop.jpg, v09-mobile.jpg, v09-mobile-source.jpg.
Preview: http://127.0.0.1:56558/ally-session-0.9.0.html.
No observed P0–P2 presentation issue remains. Cross-browser and assistive-technology certification is not claimed. Current model evidence limits are preserved beside the relevant content and in Coverage.

---

# Session report design QA

Status: passed

October 14, 2026. This status covers the report implementation and the exercised browser behavior. It does not certify Claude's diagnosis or establish superiority over `/insights`.

## Reference and scope

The supplied report image was inspected before implementation. Its white document layout, compact hierarchy, thin separators, restrained links, turn table and single proposal location were implemented in the existing Python exporter. The reference and the final actual report were viewed together at 1487 × 1058. No mockup findings, numbers, skill names or recommendations were copied into the product.

The latest actual report is `.analysis/previews/ally-session-0.5.0-reviewed.html`, served locally at `http://127.0.0.1:56558/ally-session-0.5.0-reviewed.html`. It renders the frozen release-check investigation. The two-sentence opening is Claude's saved text, including its limitations; there is no renderer summarization step. The longer opening and 32-turn table reflect real content rather than the reference's short synthetic example.

## Browser checks

| Check | Result |
| --- | --- |
| Desktop 1487 × 1058 | Flat hierarchy, readable type, restrained separators and compact metrics; no dashboard cards, sidebar or decorative graphics. |
| Tablet 768 × 1024 | Document width equals viewport width. Long title and requests wrap; all metrics remain available. |
| Phone 390 × 844 | Document width equals viewport width. Metrics wrap; the turn table pans within its own labelled region. Expanded content and source dialog fit the viewport. |
| Actual saved opening | User intent and recorded work appear before metrics. Incomplete status, unverified outcome and unread evidence remain visible. |
| Missing data | Unknown usage stays unknown, with known subtotal/coverage where supplied. Cached tokens remain included in input; elapsed spans are not presented as active work. |
| Long request/source | A 5,365-character synthetic request retains its ending in expanded text and in the source dialog; the shortened table preview is literal. |
| Multiple findings/proposals | Separate finding links open exact saved claims and qualifiers. Related turns link to one proposal; recommendation wording is not repeated in turn rows. |
| Original evidence | The actual finding opens the original test failure, member/line identity, adjacent records and paired tool input. Back-to-finding and Escape work. |
| Turn patterns | Real classifications, shares, member turns and recorded failures expand. Selecting member turn 32 opens that turn and its original records. |
| Zero recommendations | Completed no-action, insufficient-evidence, incomplete and not-run fixtures show distinct states. The actual incomplete investigation has zero proposals. |
| Exact copy | Replacement text matches the saved string, including quotes, shell-like text, tags, Unicode and a trailing newline. Invocation copies only the exact invocation. No file is applied. |
| JSON export | Downloaded JSON is deeply equal to the saved report payload. |
| HTML export | Downloaded payload equals the saved payload. Reopened export restores expanded content once: 20 records, then 40 after paging, without duplicates. Evidence remains usable. |
| Runtime | No console errors or warnings observed in the exercised final report and export round trip. Temporary viewport override reset. |

The synthetic cases live under `.analysis/previews/qa-v05-final/` and are visibly labelled as synthetic. They exercise UI states, not model diagnostic quality. The source-projection disclosure policy still applies; full raw thinking/media/environment payloads are not silently embedded.

## Evidence and unresolved limits

Screenshots: `.analysis/previews/v05-final-desktop.png`, `v05-final-tablet.png`, `v05-final-mobile.png`, and the separate exact-edit fixture capture. The authored-output equality audit is `.analysis/report-render-audit-0.5.0.json`. Release and live-run results are documented in `docs/validation.md`.

No observed P0–P2 report implementation defect remains in the exercised cases. Keyboard and screen-reader coverage is limited to semantic controls, labels, focus behavior and dialog dismissal; this is not a full accessibility certification or cross-browser matrix.

The actual Claude investigation remains partial and contains a factual mismatch: it says 17 missing child traces; the captured scope has 16 distinct missing child identities. The validation policy flags this beside the original sentence. The wording is preserved. The narrow literal check cannot validate arbitrary prose, and most middle turns remained unread by Claude's choice. These are diagnostic-quality gaps requiring further evaluation, not visual issues to conceal.

## 0.5.1 failure details

Status: passed

Nonzero counts in the pattern table now open the exact counted requested invocations. Browser checks on the actual saved report verified both three-invocation groups, literal result previews, full original results and inputs, back-to-failures, Escape dismissal and turn links that close the dialog and expand context. Existing finding-to-source/back navigation still works. Zero counts remain plain text. The full saved report payload is unchanged.

At a 390-pixel viewport the dialog is 372 pixels wide, with no horizontal document overflow. All entries remain available through dialog scrolling. Normal viewport sizing was restored. No console errors or warnings were observed. Screenshots are `.analysis/previews/v051-failures-desktop.png` and `.analysis/previews/v051-failures-mobile.png`. The 65 scoped Python tests and JavaScript syntax check passed; the new regression exercises failure membership and disclosure rather than treating a failed call as a diagnosis.


## 0.7.0 failure explanations and subagents

Status: passed for the exercised UI behavior; model diagnosis limitations remain.

The actual report is `ally-session-0.7.0.html`. All saved Claude fields equal the frozen follow-up investigation; seven saved failure-explanation records represent six active attempts and one preserved revision. Both nonzero main-pattern groups open their explanations and original evidence. Source and back navigation work. The actual child invocation opens its assigned task and parent evidence with an explicit unavailable child trace; no child work or usage was invented.

The clearly labelled synthetic child fixture exercises automatic collection, a captured child, a nested child, an unavailable child and exclusion of an unlinked child. Main rows and metrics contain only the main agent. Clicking the invocation opens task text, separate child metrics, parent-reported totals labelled non-additive, the last captured assistant message, nested invocation links and paged source records. The child failure control opens the corresponding counted invocation. Returning from a child source preserves context. Pagination advances from 20 to all 35 records.

At 390 × 844, document width is 390 pixels and the child dialog is 372 pixels (370 client and scroll width); no horizontal overflow was observed. The temporary viewport override was reset. An HTML export retained the same JSON payload; after reopening, child pagination rebuilt 20 then 35 rows without duplicates. No console errors/warnings were observed in these checks.

Screenshots: `.analysis/previews/v07-subagent-desktop.png`, `v07-subagent-mobile.png`, `v07-actual-missing-child.png`, and `v07-failure-explanations.png`. Synthetic screenshots demonstrate UI behavior, not real developer analysis. The actual model report remains partial and includes a misstated shell-quoting cause and overgeneralized correction claims, documented in `docs/validation.md`; no renderer or Codex edit concealed them. This is not a full accessibility/cross-browser certification or an Ally backend deployment.

## 0.10.4 follow-up — October 15, 2026

The renderer is unchanged. Fresh Claude-authored citation explanations and the native CSV investigation were inspected in the browser. The source sentence, exact paired input/result, revised requirement map, all five token categories, no-proposal state and JSON export were exercised. The exported JSON deep-equals the saved output. Keyboard activation copied the exact retained result after an initial AX activation returned stale clipboard contents; both observations remain in the record.

Current viewport override attempts did not change measured dimensions, so the new screenshot is not claimed to be a narrow-screen check. The earlier 390×844 screenshot and full responsive checks remain applicable to the unchanged renderer. Temporary overrides were reset and the user's original report restored. Evidence: `.analysis/audit-0.10.4/browser-checks.json`, `native-csv-source.jpg`, `source-explanation-desktop.jpg`; prior narrow screenshot: `.analysis/audit-0.10.3/mobile-source-inspector.jpg`.

The audit also records product issues rather than disguising them: SDK-origin requests produce an empty turn table; a bundled completed requirement includes a missed sub-instruction; an incident's expectedness qualification requires opening its saved review. See `docs/developer-usefulness-audit-2026-10-15.md`. Claude-authored wording was preserved.


## 0.11.0 session library

Retained the report renderer inside a local library shell. Last-two-component folder names, full-path disclosure, search/filter, 60-row pagination, report versions, local previews and explicit investigation controls were checked. Two identical short folder labels retained different full-path filter identities. Browser export initially failed inside the iframe; registered saved-file downloads fixed it, and both formats matched exact bytes. A 390×844 check found no outer overflow and retained readable report/source controls. The report's existing horizontal table scrolling remains intentional. Screenshots and checks are under `.analysis/audit-0.11.0/`.


## 0.11.1 — Source inspector controls

Added compact Expand/Restore and Collapse controls, plus a Source control to reopen the retained view. Verified the actual migration report in docked, full-width and 390×844 views. Selection, exact copied text, wrapping and inspector scroll persist; the original finding dialog returns on collapse. Controls remain sticky while reading long results. No source text, metrics or saved Claude prose were rewritten. Evidence: `.analysis/audit-0.11.1/source-docked.jpg`, `source-expanded.jpg`, `source-narrow.jpg`.


## 0.11.2 — Thinking source states

Verified the supplied empty-thinking record with the actual timestamp, an exact empty-field explanation and response-wide usage. No empty code panel, line gutter, Copy or Wrap appears. Adjacent tool evidence restores its ordinary controls. Synthetic retained thinking displays in a separate source panel and copies the exact masked string; provider redaction, absent fields, unsupported blocks, omitted media and no-source exports have different notices. Mixed text/thinking keeps both sections.

The 390-pixel DOM/layout check passed after reopening the inspector (modal, full width, no outer overflow). Screenshot capture was unavailable at that size; do not treat it as a visual pass. Desktop proof and format receipts are under `.analysis/audit-0.11.2/`. Claude's saved findings were not edited.
