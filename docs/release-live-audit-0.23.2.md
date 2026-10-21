# 0.23.2 release validation — held for Claude quota

The local candidate is `dist/ally-session-analyzer-0.23.2.zip`, SHA-256
`e9cafd6b08fa2c8afa27fabff05ddcf21112f9c4429588e683cd0e0e1ecb6e71`:
136 members, 564,423 bytes, built from `9a575d889ff056fb645fa7798c36ad8ac463fe2b`.
Every packaged member matched its source at freeze time. The earlier 0.22.2,
0.23.0 and 0.23.1 archives remain unchanged. Nothing from this candidate has
been pushed or distributed.

## Completed offline checks

- Full suite: **447 tests run, 445 passed, two optional private-fixture skips**.
- Targeted source-first, historical wording, delivery, concurrency and packaging
  checks: **61 passed**, including the seven clean-extraction/process checks.
- Claude plugin validation passed with the documented plugin-root `CLAUDE.md`
  warning. Clean local marketplace installation and the actual installed MCP
  handshake passed: six internal skills, one reviewer agent and 62 tools.
- The single public command is `/analyze`, installed by the managed shortcut
  script. Other skills are internal. Single/multiple paths, `--separate`, focused
  follow-ups and requested saved-report/browser workflows use that entrypoint.

The new review API withholds a v2 draft's authored body until fresh request and
instruction-context reads are complete. Missing-range hints preserve progress
without crediting reads before the original draft boundary. Legacy views,
original bodies, markers, rejected/accepted history and the two-submission cap
remain intact. Ready responses add a UTF-8 checksum and explicit literal-delivery
instructions; they never rewrite the accepted text.

## Live status

| Final-package flow | Status |
| --- | --- |
| Combined four logs | Started; stopped by provider HTTP 429 during source review. |
| Separate output for four logs | Started; stopped by provider HTTP 429 at reviewer startup. |
| Single log | Pending on 0.23.2. |
| Interrupted review / same-reviewer resume | Pending on 0.23.2. |

Both blocked hosts reported `usage_limit_reached` and a reset at **5 a.m.
America/Detroit**. No account, provider or model workaround was attempted, and
no further paid runs were started. The combined trace shows the new draft gate
withholding authored prose while 48 sources remained unread in the fresh review.
It recorded four reviewer model responses with usage before the quota error.
The separate run recorded a native spawn/handle but no usage-bearing reviewer
response. That is missing completion telemetry, not proof of zero provider cost.

Each run retained one draft and one native reviewer handle, zero review
submissions, unchanged source accounting, original source bytes and the tested
archive hash. Both executed-tool policy checks passed. Output/readiness gates
remain incomplete; a false `review_submission_limit` flag here means no review
was submitted, not that the cap was exceeded. Host estimates were $1.9885323 and
$1.7516512 respectively, separate from analyzed-source cost and not invoices.

Earlier single/resume successes on 0.23.1 cannot clear the changed final package.
The [0.23.1 audit](release-live-audit-0.23.1.md) preserves the failures that led to
the source-first and exact-delivery changes; the [0.23.0 audit](release-live-audit-0.23.0.md)
preserves the oversized-guide/helper failure.

## Resume after confirmed quota reset

Private evidence is under `.analysis/claude-release-0.23.2/` in
`combined-iwjq5d81/` and `individual-bfpjqdrn/`. Each `resume-state.json` retains
the original host session, native reviewer ID, exact draft and freshness markers,
package/source/accounting fingerprints, scope environment, a conservative
remaining test allowance and same-session resume argv. Do not import again,
create another draft, reset markers or launch a fresh reviewer. Append new stage
files and continuation audits; preserve the original transcripts, answers and
failed audits. Reconcile all stage traces and verify actual same-ID continuation,
fresh native coverage, the exact accepted answer and unchanged fingerprints.

Then run the pending single-log and interrupted-review/resume checks on this
same immutable package. Inspect the actual claims against the source, especially
the retained instruction and sibling-message distinction in a8. Release remains
held until all four final-package flows pass; source review is not a correctness
certificate for future sessions, models or hosts.
