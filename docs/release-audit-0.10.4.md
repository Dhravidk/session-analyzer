# Release audit — 0.10.4

October 15, 2026. This is a locally tested Claude Code plugin candidate. Authentication now works and two fresh investigations completed. The live examples also exposed interpretation and coverage weaknesses; they do not establish production readiness or superiority over `/insights`. See the [developer usefulness audit](developer-usefulness-audit-2026-10-15.md).

## Workflow correction

Claude Code's print mode can consume piped stdin as well as its explicit prompt. A synthetic-session launcher inherited its parent Python input, and the native log proved that launcher code was appended to the intended request. The managed investigation runner had the same latent exposure. `run_host` now uses `stdin=subprocess.DEVNULL`; runner attestation is v5. A regression passes an unrelated parent-pipe sentinel through the real subprocess boundary and verifies that the child receives only the explicit prompt.

The contaminated attempt remains in `.analysis/audit-0.10.3/claude-created-session/`. It is not used as clean validation evidence. A new isolated project and native session were created with stdin closed. The two saved native requests were compared exactly with their intended request files. No code or prose produced by Claude was repaired by Codex.

## Mechanical checks

- 205 backend tests passed in 21.519 s with both optional supplied corpora enabled. Log: `.analysis/tests-0.10.4.log`.
- The new stdin regression exercises the process boundary, not a mocked `Popen` assertion.
- Existing clean-archive, isolated MCP startup, disclosure, accounting, requirement, recovery, scope and review tests remain in that suite. The [0.10.3 audit](release-audit-0.10.3.md) records the broader browser cases on the unchanged renderer.
- The native synthetic project finished with six passing tests. The operator independently reran the final suite. Initial tests were unchanged after the first repair; the second request added three BOM tests.

Final package validation and byte comparisons are recorded separately in `.analysis/audit-0.10.4/package-validation.json`. The immutable package used by the live native investigation is retained in its work directory. Documentation updates after that run must not be represented as another model execution.

## Observed Claude behavior

| Run | What actually ran | Observed result | Limits |
| --- | --- | --- | --- |
| Source explanations, 0.10.3 attempt 3 | Synthetic red/green fixture; guided request to exercise citation explanations; separate investigation and review hosts | Completed, no action supported; all 31 checked active reference occurrences had a saved explanation; one failure explained | Presence is not quality. Thin explanation accepted; repeated caveats. One unknown tool name rejected. |
| Native CSV, 0.10.4 | Claude Code generated a two-request synthetic coding session; analyzer used its default unanchored question and four admitted file snapshots | Completed, no action supported; identified duplicate Edit anchor and permission denial; did not use the interim three-test pass as proof of the new BOM tests; reviewer revised the requirement map | Bundled completion status hides a missed sub-instruction. SDK requests excluded from turn population. Available final snapshots not inspected. Two placeholder tool names rejected. |

The first run used 36 recorded analyzer calls, 190.020745458 s elapsed, and $1.1082006 host-reported cost. The native investigation used 35 calls, 215.261962625 s, and $1.3345888000000001 host-reported cost. These are observations for two examples, not typical-cost estimates. Source-session usage remains separate.

Both runs loaded the writing skill and completed a fresh review process. Saved incidents, requirement maps, explanations, conclusion drafts and recommendations match the recorded Claude tool inputs. Standard HTML export matches; canonical source accounting was unchanged. Executed calls stayed within policy, but `allowed_calls_only` is false because unavailable tool names were attempted and rejected. All raw transcripts, revisions and negative checks remain intact.

Evidence directories: `.analysis/claude-examples/source-explanations-0.10.3-attempt3/`, `.analysis/claude-examples/native-csv-0.10.4/`, and `.analysis/native-sessions/csv-0.10.4/`. The last contains the actual native JSONL, launch requests, before/after project snapshots and admission manifest. This is synthetic work performed by Claude Code, not Ally production data.

## Browser observations

The fresh source explanation appears beside its exact paired input/result. Keyboard activation copied the complete saved result exactly. An initial background AX activation showed a success notice while the clipboard stayed stale; it is retained as an automation observation, not silently counted as a pass. The fresh native report exposes its revised requirement map, all five token categories, zero recommendations and unattributed finding. Its SDK-origin limitation is visible: zero user turns and nine unassigned responses.

The current viewport override did not change the measured preview dimensions, so no fresh 390 px result is claimed for this follow-up. The unchanged renderer's earlier 390×844 tests and screenshot remain the responsive evidence. Details and screenshots: `.analysis/audit-0.10.4/browser-checks.json` and `.analysis/audit-0.10.3/`.

## Release boundary

The conventional plugin structure, local engine and controlled investigation workflow can be evaluated now. Broad release still needs independently labelled sessions, semantic quality review, an explicit policy for SDK-origin task coverage, and validation on the Ally laptop. No Ally schemas, historical plugin versions, authentication or deployment compatibility are inferred from these local tests. The supplied developer report remains the original completed investigation rendered with the new presentation; it has not been silently regenerated.

The updated PM deck is `output/Ally-session-analyzer-PM-0.10.4-reviewed.pptx`. It preserves the earlier editable design and system diagram, adds the stdin boundary, and replaces the sign-in blocker with actual live findings and remaining quality work. The private build directory retains the prior deck, revisions, renders and validation receipts. Native PowerPoint rendering is not certified.
