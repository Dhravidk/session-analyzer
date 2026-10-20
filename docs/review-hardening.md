# Reply-review persistence and subprocess hardening

Both single-session and collection review entrypoints use `reply_review.save_review` for the final append. That helper acquires SQLite's writer reservation with `BEGIN IMMEDIATE`, rereads the draft's persisted review history on that connection, applies retry/acceptance/attempt rules, and appends on the same connection before committing. A process-local lock is not used. An optimistic retry lookup can avoid repeated validation but never authorizes a new append; the transaction always rechecks history.

Source/body validation remains outside this short transaction because those functions open their own connections for source caches and access logs. Holding the writer reservation while calling them would risk self-blocking. A failed append rolls back without consuming a submission slot. No separately reserved slots, acceptance flags or schema migration are needed. Keep both production entrypoints routed through this guarded append rather than using bare `put_record` to admit a review. `put_record` and `records` accept an explicit connection so the append and authoritative history read share one transaction.

The rules retain the existing contract:

- One accepted answer per draft for new submissions; a different submission cannot replace it.
- At most two distinct submissions, including rejected attempts. Identical rejected retries reuse a saved attempt when exposure is unchanged; fresh exposure can permit a revised validation attempt within the remaining slot.
- An exact accepted retry reuses its immutable accepted review regardless of later exposure.
- Historical drafts, rejected attempts, accepted reviews, timestamps and authored wording are not rewritten. If a legacy store already contains conflicting acceptances, the first review in its established stored ordering remains the canonical answer. Later conflicting historical rows remain available for audit but cannot become a second ready answer through retry. Existing excess attempts are retained and prevent new submissions.

The shared module also owns fresh request/update coverage, literal quote checks and source-review issue rules. Coverage, retry exposure keys and quote-read IDs use one captured access snapshot per root. The existing exposure projection is factored into a public pure helper rather than reimplemented. Collection orchestration still selects/tags each member separately, authors no findings, and validates its complete synthesis separately from the single-session body flow. These checks establish linkage, not semantic correctness or native reviewer identity.

The packaged-process test helper uses bounded nonblocking stdin/stdout with selectors, line-size limits and deadlines. A context manager terminates, escalates to kill when required, waits for the subprocess, and closes its streams even after timeout, parse errors or assertion failure. Stderr goes to a temporary file so an unread stderr pipe cannot block the child. This POSIX test helper supports the documented macOS/Linux development workflow and is excluded from the plugin archive.

## Offline checks

```sh
python3 -m unittest tests.test_review_concurrency tests.test_session_reply_review tests.test_session_collection tests.test_session_reading tests.test_packaging_process tests.test_packaging -q
python3 -m unittest discover -s tests -q
python3 -m unittest tests.test_packaging_process tests.test_packaging -q
```

The concurrency tests spawn separate Python processes sharing an actual SQLite store. They synchronize after real validation, then exercise the actual public submission and persistence paths. They cover conflicting answers, identical accepted/rejected retries, competing final accepted/rejected/mixed attempts, retrieval, rollback on an actual failed insert, and byte-preserved legacy history. Persistence is not mocked. As a negative control, the conflicting-answer and competing-final tests fail on the previous committed implementation in both workflows.

Synthetic subprocess cases cover an unresponsive process that ignores termination, partial and oversized unterminated responses, blocked stdin, early EOF and an assertion failure. They invoke Python, never Claude. The extracted-package test uses the same bounded client for actual MCP calls. Neither synthetic review acceptance nor a process test certifies model-written findings or reviewer provenance.

Final live single-log, combined-log and separate-output checks remain pending until the user explicitly confirms the Claude limits have reset. Do not invoke Claude for validation before then. Keep candidate archives, private logs, stores, generated reports and test outputs out of Git; do not push or distribute.
