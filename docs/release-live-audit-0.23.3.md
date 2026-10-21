# 0.23.3 validation — offline pass, live release held

The local candidate is `dist/ally-session-analyzer-0.23.3.zip`, SHA-256
`fbf5533a029063366d33bdd1e00149e6210d87cfa1b424146cd28b9fd5496490`:
136 members, 566,604 bytes, built from
`d605dc5a8f98c34de3f6fa016d56a440ca45ac17` after the offline checks passed.
Every archive member matched its committed source at freeze time. The older
0.22.2, 0.23.0, 0.23.1 and 0.23.2 archive hashes remain unchanged. No candidate
or new commit has been pushed or distributed.

## Default presentation

New general readouts start with the total estimated source-session cost only.
Token/component breakdowns and routine pricing-verification/subscription,
separate-host-estimate and reconciliation notes remain accessible through
`session_readout.token_summary`, `usage`, `cost_details_on_request` and existing
scoped tools. Each selected member's overview retains its full `source_cost`.
Collection readouts retain the union breakdown and reconciliation notes.

The initial ready reply does not append those routine notes. Unavailable cost,
partial pricing and material missing-trace/snapshot-freshness limits stay
explicit. The four token categories, rate selection, arithmetic, tool inventory,
compliance assessments, disclosure controls and implementation-approval boundary
are unchanged. The skills, native reviewer and MCP instructions use this policy.

Saved drafts retain their original computed cost presentation on resume,
including older four-category openings. The single-session acceptance path now
uses that saved readout, matching collection behavior. Original drafts, rejected
attempts, accepted reviews and exact authored bodies are preserved. The new
display is not applied retrospectively to historical answers.

## Offline evidence

- **449 tests run: 447 passed, two optional private-fixture skips.**
- **80 focused tests passed**, including seven clean-extraction/process checks.
  The final full suite also covers concurrency, draft registration, native
  reviewer reservations and the public `/analyze` entrypoint.
- Synthetic single, combined and separate-output flows verify the shorter
  ready reply, retained follow-up accounting/notes and unchanged authored text.
  A display-upgrade regression preserves a saved draft's cost presentation,
  earlier rejected attempt and subsequent accepted wording.
- The clean-extracted MCP exercised draft/review/retrieval and follow-up data
  through the actual stdio entrypoint. Default notes are absent from the ready
  reply, while accounting remains available after retrieval.
- All four explicitly selected real logs passed offline verified-pricing,
  source/accounting-preservation and prior-output-hash checks with network and
  model subprocesses blocked. Both saved real collections retained identical
  token/component accounting and cost notes, with unchanged drafts/markers.
  These are computed previews, not newly authored Claude answers.
- Native plugin validation passed. The extracted installation smoke check
  registered **62 tools** with disclosure off, no source import and no model
  invocation. The validator retains the documented plugin-root `CLAUDE.md`
  warning and advisory about a marketplace-install line in the extracted README;
  neither changes its passed verdict. The packaged skills carry runtime guidance.

Private artifacts remain in `.analysis/`: the `cost-display-0.23.3-*` test and
preservation records, `candidate-0.23.3-build.json`, extracted smoke-check and
validation records, and offline pricing previews. None is packaged or tracked.

## Live release blockers

After the operator confirmed quota reset, both saved **0.23.2** batch reviews
were continued with their original host, collection, draft and native reviewer
IDs. Single-log and interrupted-review tests also started against that exact
frozen archive. At approximately **1:24 a.m. America/Detroit on October 21**,
all four immediately returned provider **HTTP 429 `usage_limit_reached`**,
still reporting a reset at **5 a.m. America/Detroit**.

No new reviewer work or source read was delivered. The batch drafts, original
markers and launch reservations remain unchanged, with no review submissions.
The single/interrupted attempts launched no reviewer. Resumed host estimates
repeated earlier cumulative totals; they are not additional charges to sum.
The [0.23.2 audit](release-live-audit-0.23.2.md) records these attempts separately
from the original failures, with append-only continuation checkpoints retained
privately for the same saved reviewers. No replacement reviewer, fallback
account/provider or subsequent paid model call was used.

| Required flow | 0.23.2 latest attempt | 0.23.3 final package |
| --- | --- | --- |
| Single log | Quota-blocked before review | Pending |
| Combined logs | Saved reviewer continuation quota-blocked | Pending |
| Separate output | Saved reviewer continuation quota-blocked | Pending |
| Interrupted review / same-reviewer resume | Quota-blocked before interruption | Pending |

Resume existing 0.23.2 batch state without resetting its boundaries or buying a
replacement review when the approved host has quota. The changed 0.23.3 package
also needs live confirmation of default/follow-up presentation and all four
final flows, with actual invocation counts, same-ID resume, fresh source
coverage, exact accepted delivery and manual claim/source review. Earlier
version successes and offline scripted reviews do not clear these gates.
Release remains held: do not push or distribute until the required checks pass.
