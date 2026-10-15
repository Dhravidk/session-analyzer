# Session navigation release audit — 0.12.0

October 15, 2026. This release extends the local session library and report renderer. It does not replace the investigation engine, rewrite saved analysis or add organizational connectors.

## Implemented behavior

The sidebar groups one entry per stable native session identity and full working directory. Native saved titles are preferred; fallback previews remain literal and the retained full request stays accessible. Folder headings use two path components, with full paths available by disclosure. Recent activity ordering, search, selection, folder/path disclosures and reading positions remain available across navigation. Narrow screens use a dismissible drawer. The single application header supplies exports; the embedded report uses horizontal navigation with Findings retained.

Only the latest saved analysis is visible for a session, including partial results. Importing older analysis later or creating a local preview cannot displace it. Original outputs, earlier reports and host provenance remain on disk. The browser has no report-version picker, history list or run counts.

Freshness compares captured agent/payload identities and relevant child metadata. Report file modification times do not decide it. Ready requires completed investigation and matching captured evidence, not a successful developer task. New activity and incomplete analysis can appear simultaneously. Missing comparison data, source changes, updating and failed updates remain explicit. Current evidence is checked on refresh and during job polling; the library is not an idle filesystem watcher.

Analyze/Update reuses the approved executable, controlled-excerpt disclosure, bounded budget/time settings and managed investigation/review workflow. The saved report stays readable and exportable during a job. Duplicate jobs are rejected server-side. A valid latest partial/completed result replaces the visible analysis; a failed update without valid output keeps the saved report and identifies the failure. Invalid or cross-session reports are rejected.

## Mechanical validation

- Full backend discovery: 236 tests, 234 passed, two optional private-corpus tests skipped; 22.112 seconds.
- Both optional private-corpus tests passed separately against the supplied log and archive; 2.521 seconds.
- Focused library regressions cover identity, deduplication, native titles, shortened-folder collisions, latest partial output, import ordering, timestamp-only changes, same-size source rewrites, missing children arriving, child metadata changes, unknown states, failed jobs, duplicate jobs, invalid report admission, HTTP boundaries and exact embedded payload equality.
- Existing investigation, token, timing, recovery, requirement, source/copy, subagent, privacy and packaging checks remain in the passing suite.

Logs are under `.analysis/navigation-0.12.0/`. After the final navigation fixes, all 16 library/packaging tests passed again, including reproducible ZIP creation and MCP startup from a clean extraction outside the checkout. Both frontend scripts pass Node's syntax check. The installed Claude plugin validator passes; its only advice is marketplace installation documentation, which is intentionally absent because no marketplace has been published. The package receipt and validator output live beside the logs.

## Observed Claude behavior

The native CSV example is a real Claude Code session for an explicitly synthetic development task. Its assistant records were not written by Codex. The browser's Update analysis action started job `8144cbf91dbb406499ca264cca8d8d5e`, from 16:05:10 to 16:12:40 UTC, with a $3/10-minute limit. The managed host reported `claude-sonnet-5-5`; an independent review stage ran. Reported stage costs total $1.9007928.

The result completed with `no_action_supported`, zero incidents and zero recommendations. The saved title is “CSV export fix and include_bom flag: code done and passing, tests not read before the first repair”. The output-origin and transport checks passed; saved authored fields match the original Claude tool inputs. The earlier report remains intact and the library still has three logical sessions. No analysis wording was edited to fit the new layout.

This run froze the 0.11.2 investigation package before the navigation release version was changed. Its tested-plugin ZIP and snapshot manifest preserve that fact. The final shell/renderer and distributable package are 0.12.0. This is observed workflow behavior on a development example, not an independent quality evaluation.

Evidence: `.analysis/navigation-0.12.0/library/runs/8144cbf91dbb406499ca264cca8d8d5e/investigation/`, including the immutable audit, report, host transcripts and tested package.

## Browser validation

The real CSV, TTLCache and supplied Angular-to-React migration reports were exercised in the in-app browser. `scripts/render_navigation_cases.py` creates a separate, visibly synthetic library through the same UI and server routes. Its controlled runner substitutes a successful/failed result without calling Claude; those fixtures validate state handling, not provider behavior.

| Scenario | Observed result |
| --- | --- |
| Multiple sessions; duplicate titles and abbreviated folders | Seven fixture sessions remain distinct; north/south `tools/cache` paths are available on demand. |
| Several saved analyses | Four initial internal analyses for one fixture produce one entry; successful regeneration changes only its visible report. |
| States | Ready, Not analyzed, Analysis incomplete, New activity, Updating, Update failed and Freshness unknown render with text and dots. New activity does not hide incompleteness. |
| Update success | Real Claude and controlled fixture runs replace the selected report without adding a navigation entry. |
| Update failure | The old report stays visible/exportable; the failure is named and the update control becomes available again. |
| Search, folders, Back | Literal title/path search and folder/path disclosure work. Session navigation restores selection and stored list/report positions. Iframe loads replace history entries, avoiding a mismatched Back step. |
| Long titles/paths | Sidebar previews wrap/truncate; full path and request remain accessible. No model-generated abbreviation was added. |
| Findings | Horizontal Findings navigation and saved finding-title controls open original finding dialogs; turn links and review qualifications remain. |
| Source inspection | Inputs/results, wrap, expand/restore and collapse/reopen work. Native source activation preserves the triggering control within 0.21 px. |
| Exact copy | A 759-character retained source was copied and pasted intact, without formatting or line numbers. |
| Export | JSON and HTML downloads are byte-identical to the original saved output; receipts in `export-checks.json`. |
| Tokens and coverage | TTL input 69,698 = 14 uncached + 11,476 cache write + 58,208 cache read; output 5,526. Main/child/analyzer populations and duration/span distinctions remain. The migration report retains 16 missing children. |
| Desktop | 1487 × 1058: single header, 330-pixel grouped sidebar, horizontal navigation, warm/plum/lavender styling and usable report/source widths. |
| Narrow | 390 × 844: document width 390, readable report text, dismissible modal drawer, inert report behind it, keyboard Escape/focus return and full-width source inspector. |

Screenshots: `desktop.png`, `narrow-report.png`, `narrow-drawer.png`, `narrow-source.png`, `desktop-expanded-source.png` and `fixture-updating.png` in `.analysis/navigation-0.12.0/`. No app console warnings/errors were observed in the final real-report checks. Browser-tool telemetry errors were external to the application and are not counted as app failures.

The final navigation regression was reproduced through actual controls: select the long-title fixture, switch to the unknown-freshness session, then use one browser Back action. The selected long-title session returns. Its expanded full-path disclosure remains open. A drawer list at 326 px remains at exactly 326 px after collapse, reload and reopening. This check caught and fixed both an extra iframe history step and a hidden-drawer scroll reset; it is recorded as browser evidence rather than claimed as a headless unit test.

## Limits and deferred work

- Freshness compares deduplicated retained payload identities, not exact file bytes or a separate ordering signature. It cannot establish that all real-world activity was captured. Older metadata manifests and incomplete/malformed imports can leave comparison unknown.
- Bounded discovery can miss a title outside the first/last inspected blocks. Divergent duplicate exports choose the candidate with latest observed activity/size; they are not silently merged.
- Large-directory first-scan performance has not been benchmarked. Hash comparisons are cached by source stat fingerprint after the initial comparison.
- Legacy report exports cannot recover richer source-omission metadata without another explicit export from retained source. The existing omission limit remains visible.
- No full cross-browser, screen-reader or accessibility certification was performed. This release checks the exercised controls and viewports.
- This scope preserved existing source paging, proposal copying and child drill-down implementation/tests; it did not repeat every historical browser scenario or generate a new recommendation to demonstrate an empty category.
- Ally-specific schemas/authentication and historical agentset artifacts are still unavailable. No Ally compatibility, population-level conclusions, measured recommendation benefit or superiority over `/insights` is established.
