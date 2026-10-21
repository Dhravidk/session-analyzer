# 0.23.1 live checks — superseded, held

All four authorized flows ran on the same frozen 136-member ZIP, SHA-256
`b95f9659c451882225e2c836bf35c44e22ddf0ea8f92c881203d423c3427aa29`.
The preceding full offline suite ran 443 tests: 441 passed and two optional
private-fixture tests skipped. The clean local marketplace installation and
actual installed 62-tool MCP smoke check passed without a model call.

| Flow | Result | Fresh source reviewers | Resume calls | Observed reviewer model responses | Saved attempts |
| --- | --- | ---: | ---: | ---: | --- |
| Single a8 | Automated checks passed; retained instruction miss explicitly assessed | 1 | 0 | 10 | One rejected, one accepted |
| Combined four roots | Incomplete review; two premature submissions rejected | 1 | 0 | 21 | Two rejected |
| Separate four roots | Accepted review, but final parent text differed | 1 | 0 | 31 | One rejected, one accepted |
| Interrupted c8 / same-host resume | All checks passed; original markers retained | 1 | 1 | 5 | One accepted |

Every flow retained one draft, one native reviewer identity, the original source
accounting, source bytes and candidate hash. No unrelated helper executed. The
guide-reference change avoided the earlier bulk-guide spill/helper failure.
The v2-to-v3 SQLite migration was also checked on a clearly synthetic store:
draft, rejected and accepted payloads, original marker and readable v2 backup
were preserved exactly.

The combined reviewer twice submitted before finishing a retained-context tail
in a8, and both bodies contained unrequested resource-topic wording. The other
three roots had complete fresh context coverage. The two-submission cap stopped
the workflow without an accepted fallback or another paid reviewer. This is a
failed default flow, not a passed review.

The separate reviewer eventually completed fresh coverage and saved an accepted
body. The parent then normalized apostrophes and split/rephrased several
sentences. Its final answer differed from the accepted document (8,372 versus
8,371 characters), so the exact-delivery check failed. Some other audit flags
depend on matching the native accepted answer; their false values must not be
read as independent proof that the visible assessments or topic omission were
absent. Both original strings remain preserved, unedited.

The subsequent candidate exposes a new draft's authored prose only after fresh
request/context coverage completes, supplies exact missing-range read hints,
and returns explicit final-document delivery instructions and a UTF-8 checksum.
Legacy draft views remain available, and the original records and two-submission
cap are unchanged. It also separates an established instruction miss from
uncertainty about cause or sibling-message delivery.

Private evidence remains in `.analysis/claude-release-0.23.1/` under
`single-t6zp1klc`, `combined-0128ucdu`, `individual-gp4m7rw4` and
`interrupted-7daor7op`. Host estimates were $1.4414983, $3.0909156 and $4.2148269
for the first three flows; interruption stages reported $0.4019742 and
$0.5814718 separately. Resumed estimates may be cumulative and are not summed.
These are test-host estimates, not invoices or analyzed-source opening costs.
The ZIP was neither rebuilt nor distributed. Release remains held pending all
four flows on the corrected immutable candidate.
