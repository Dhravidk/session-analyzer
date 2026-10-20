# 0.22.2 live release checks — held

On October 20, 2026, the operator confirmed that Claude limits had reset and authorized the four pending live checks. All four ran through the approved local Claude Code host (2.1.299, resolved model `claude-sonnet-5-5`). The immutable tested candidate is `dist/ally-session-analyzer-0.22.2.zip`, SHA-256 `87e5ad27f722e868abf7b48e7eae08dd579233f4686809d56d5fd4c349f6c9d4`. No runtime, skill, reviewer, renderer or pricing change was made during these tests. The ZIP was not rebuilt, pushed or distributed.

The live checks used deterministic import and explicit investigation/collection binding, then the default conversational explain/review handoff. The single check used a8; combined and separate-output checks used the four explicitly selected Nithin logs; interruption used c8. This tests the scoped native handoff, not every import-selection path, permanent installation, other models or platforms. All original sources and all 120 packaged members still match their saved hashes/current source bytes.

## Actual reviewer activity and results

| Flow | Automated result | Fresh reviewers | Resume calls | Reviewer model responses with usage | Saved review attempts |
| --- | --- | ---: | ---: | ---: | --- |
| Single log | Failed default-topic omission | 1 | 0 | 9 | 1 accepted |
| Combined four logs | Passed | 1 | 0 | 10 | 1 rejected, 1 accepted |
| Separate output for four logs | Passed; manual compliance concern below | 1 | 0 | 16 | 1 rejected, 1 accepted |
| Interrupted review, then host resume | Failed reviewer reuse | 2 | 0 | 7 | 1 accepted |

These counts come from actual `Agent` calls, distinct native child IDs, host task/spawn records and child model messages with reported token usage. Streaming frames are deduplicated by child/message ID. One reviewer makes multiple model requests; a corrected submission does not imply another reviewer. These are observed usage-bearing responses, not an independently reconciled provider invoice. Interrupted in-flight requests can lack final usage.

All four flows retained exactly one draft and one accepted answer. The final answers copied their native accepted replies verbatim, started with the exact computed source-cost/token breakdown, exposed separate authored task-outcome/instruction-following assessments, stayed within executed-tool policy, and left source accounting and original logs unchanged. Fresh read IDs from actual native child results cover all indexed requests/updates for each selected root. This exposure check does not establish complete instruction coverage or semantic correctness.

Combined and separate-output reviewers each corrected one rejection for unrequested compaction detail, within the two-submission limit and using the same native reviewer. Both rejected versions remain saved. No unreviewed fallback was used. The single-log reviewer instead included a reference to a post-compaction summary in its accepted default body. The current heuristic in `session_readout.py` did not reject that phrasing. The stricter live omission check correctly fails it; the answer has not been edited or replaced.

## Interruption and real paid restart

The harness sent SIGINT only after a native source-read result had been delivered. The host recorded that reviewer as killed by the user. The second turn resumed the same Claude host session with a request to continue the same draft/reviewer. It nevertheless made a new `Agent` call without a `resume` target and started a different native child. Both calls name the same persisted draft.

The interrupted child made two recorded model responses with usage; the replacement made five. Each independently reread all indexed c8 requests. This is actual repeated reviewer activity, not an inference from duplicate rows. The final draft equals the saved interruption snapshot, including all original freshness markers, and exactly one review was accepted. Atomic SQLite registration/acceptance worked, but it did not deduplicate host launches or implement native reviewer resume.

The normal host-reported test costs were $0.8601335 (single), $1.4685306 (combined) and $1.4469585 (separate). The interruption and resume stages separately reported $0.4359829 and $0.609703; these stage values are retained without assuming additive resumed telemetry or attributing the entire stage cost to a reviewer. These test-host figures are excluded from the analyzed-source openings. They are not subscription invoices.

## Manual compliance concern

The separate-output a8 body says no instruction violation is established, relying on the later human go-ahead being a sibling rather than an ancestor of the final response. That branch qualification is supported, but it does not dispose of other applicable instructions. The retained resume summary at source line 542 is an ancestor of the final assistant response at line 630. It instructs continuation without further questions and describes writing the plan documents before the approval gate. The single reviewer reread the relevant summary tail; the combined and separate-output native read traces contain no controlled read of that source. The earlier full skill snapshot is also captured at line 45, outside the retained post-boundary parent chain.

The separate-output compliance clearance needs revision or qualification against that counterevidence. Do not transfer the sibling human authorization into the response, infer remote file absence, or treat an indexed-request coverage pass as a complete check of historical skills/resume instructions. This is a further source-review quality blocker, distinct from the automated format/provenance results. The original Claude answers remain unedited.

## Evidence and regression checks

Private evidence stays ignored under `.analysis/claude-release-0.22.2/`:

- `single-kogbh0ct/`, `combined-p5o9ce7f/`, `individual-lm6rbsxy/` and `interrupted-mxhus941/` retain the exact tested ZIPs, argv, prompts, raw transcripts, stderr, answers, stores and per-stage/final audits.
- `final-live-audit.json` reconciles all four runs, hashes, reviewer counts, saved histories and failing checks.
- Each run's `independent-native-coverage.json` checks only fresh read IDs actually linked to native children. This supplemental check was applied after the first runs; their original audits were preserved.
- `interrupted-mxhus941/per-reviewer-resume-audit.json` separates the two children and repeated request reads; `interrupted-drafts.json` preserves the original boundary.
- `instruction-exposure-check.json` and `instruction-ancestry-check.json` support the manual compliance concern without rewriting the source or the model's answer.

The development-only `scripts/test_claude_release.py` accepts the exact candidate ZIP and runs single, combined, individual or interrupted modes. It preserves bounded process capture and intentional interruption separately from ordinary success. Its eight offline tests cover child linkage, usage-frame deduplication, resume identity, rejected parent/unrelated provenance, visibility of duplicate fresh launches, native-only fresh coverage, interruption capture and timeout cleanup. The full offline run discovered **419 tests: 417 passed and two optional private-corpus tests skipped**. The separate clean-extraction/package-process run passed **7 tests**. Evidence is in `.analysis/claude-release-harness-offline-tests.log`, `.analysis/claude-release-harness-final-full-offline-tests.log` and `.analysis/claude-release-harness-clean-extraction-tests.log`. No private source, answer, store, trace or archive is committed or packaged.

## Release blockers

1. Persist a native reviewer handle at launch and use an explicit same-reviewer resume path across interruption. A saved draft ID and an instruction to resume are insufficient. Verify the actual native launch/usage traces after the fix.
2. Close the default-topic validation gap on newly submitted reviewer bodies. Reject the observed unrequested phrasing for author correction; do not filter or rewrite historical Claude output in the renderer.
3. Review applicable captured skill/resume instructions as well as indexed task requests before issuing a clean compliance assessment. Recheck the a8 counterevidence and retain the sibling-authorization uncertainty.

All four original live checks have now executed; they are not waiting for quota reset. Release remains held for these failures and targeted reruns after fixes. No distribution or push is authorized.
