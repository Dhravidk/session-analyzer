# 0.19.0 release evidence

This update makes task delivery and adherence to evidenced instructions visible near the start of the developer's Claude reply. It preserves required developer approval before implementation, the computed cost/four-count opening, all underlying accounting and historical authored output. The server does not generate compliance verdicts or edit findings.

## Changed behavior

- A general reply includes separate authored task-outcome and instruction-following assessments. `prepare_session_reply.compliance` contains their exact visible spans; omitted, private-only or identical assessments cannot produce a ready reply.
- With content disclosure enabled, the whole-session readout requires full delivery of captured main-task requests, including source continuations. The overview and preflight return counts and up to eight unread IDs. This catches skipped later permissions without requiring every assistant step or a full saved report. Metadata-only scopes keep their existing disclosure policy.
- Structured queued prompt attachments are included in the request and requirement-map inventories, separately from ordinary requests. They retain captured-human or unverified origins without becoming new reconstructed turns or changing token totals. A reminder-like string in ordinary tool output is not automatically indexed as a human request. Relevant results can still carry updates requiring source review.
- Default bodies are limited to 450 words; Claude revises an overlong draft rather than the tool truncating it. Detailed saved reports remain unchanged. Focused follow-ups answer their question directly.
- Guidance checks timestamps and recorded parent branches before attributing an ignored authorization. An earlier message on a sibling branch does not prove delivery to a later model response. Pending-work admissions remain attributed statements; unavailable external files are not proof of nonproduction. Exact skill edits still require inspected target snapshots.
- The existing topic preflight also catches resume advice mentioning `/compact` or activity before/after compaction. Default replies keep resource detail on request, while the cached-input opening and all existing evidence, metrics and tools remain available.

## Test scope

Offline tests cover exact body preservation; missing, private-only, identical and malformed assessments; unread and partially delivered authorizations; bounded refreshable request previews; metadata-only behavior; default length rejection; resource-detail rejection; retained accounting/tools; and sibling authorization branches. A full delivered request inventory remains exposure, not proof of model input delivery, comprehension or fulfillment.

The opt-in `scripts/test_claude_developer_reply.py` uses an explicitly selected log, the approved local Claude host and restricted scoped readers. It preserves the immutable tested ZIP, generic question, argv, raw transcript, unedited answer, host model/usage and audit under ignored `.analysis/claude-developer-reply/`. It cannot execute archived commands or alter saved judgments. These are native conversational answers, not completed independently reviewed investigations.

## Earlier trials retained unchanged

The first planning-log run, `run-7jp63seo`, passed the cost opening and visible-assessment checks but volunteered resource detail and missed the clearest later authorization. That motivated the resource-pattern regression and request-delivery prerequisite.

`run-cisn3r1c` passed mechanical checks after one preflight correction but still misstated chronology and overclaimed nonproduction in its opening. `run-77ye10bz` also passed mechanical checks but used an incorrect rounded interval and blurred the approval distinction. All outputs remain unedited. Source review also found that the decisive authorization and final response occupy different recorded parent branches, so chronology alone cannot establish that the model received and ignored the authorization. The guidance now requires examining that distinction.

Collection-log runs `run-h9k5tqnf` and `run-h1oyd48r` kept the missing copy result unverified. The latter nevertheless called all seven Bash invocations read-only, although the final invocation attempted a copy, and included unnecessary speculative advice. These are semantic failures that the formatting preflight did not detect. The default length limit and tighter evidence guidance do not constitute a semantic guarantee.

High-effort trials `run-oyhpiebi` and `run-czm4xju2` both passed mechanical checks. The planning reply distinguished sibling-branch authorization from proven model disobedience. The collection reply found a structured queued human update requesting the added cross-project scope; previous replies had missed it and called that scope possibly unrequested. That motivated including these structured sources in request and requirement-map coverage. The final-runtime reruns are recorded below. Effort was a test-harness choice, not a changed user setting or a controlled experiment establishing an improvement from higher effort.

## Final-runtime examples and source review

The final-runtime native runs were `run-9cptgall` (planning) and `run-nhzjnpxy` (collection). Both passed all nine mechanical checks with the current runtime and skills. The planning run fully delivered 14 ordinary request sources and had no structured updates. The collection run fully delivered one ordinary request and one captured-human queued update. One unknown-tool attempt in the planning run was rejected, not executed; it remains in the audit.

The planning first-pass answer still proposed repeating an adequate skill instruction. Both answers therefore received a fresh approved-Claude source review, preserving the original answers. Each review reread decisive evidence through the scoped tools; it did not edit prior output or saved findings. The planning review withdrew the duplicate-rule advice and preserved uncertainty about authorization delivery. The collection review traced the queued update upstream of the Jacob search, established the recorded source of the selected sessions, and kept the missing copy result unverified. A final Claude writing turn produced standalone messages without editorial draft-history sections. Every intermediate answer and prompt remains under each run's `source-review/` and `final-readout/` directories.

Both source-review and final-readout stages passed their eight preservation/format/tool-policy checks: successful host, exact cost/token opening, verbatim ready reply, default topic scope, unchanged canonical accounting and source log, unchanged prior answer, and executed calls within policy. The displayed examples are the exact `final-readout/answer.md` files, not Codex-rewritten excerpts or first-pass unattended-quality claims. Critical source checks confirmed the planning log's sibling branches and pending-work statement, the collection log's structured human update and final copy attempt without a result, and unchanged cost/token accounting. The collection source has no usable recorded cost, so its opening says unavailable rather than inventing a bill.

The full offline suite discovered **341 tests: 339 passed, two optional private-corpus tests skipped**. Twenty-four developer-readout cases include the new coverage and preservation regressions. An earlier targeted command named a nonexistent test module and failed to import it; the final discovery run passed the actual suite. No failure was converted into a pass.

## Distribution checks

The private ZIP contains 105 implementation/documentation files. All 82 runtime/skill members match the immutable ZIPs from both source-review and final-readout stages byte for byte. Raw logs, analysis stores, generated answers, live QA harnesses, credentials and test fixtures are excluded. Native `claude plugin validate --strict` passed. Its marketplace-install advice is nonblocking; no marketplace is configured, so the documented `--plugin-dir` route is retained instead of inventing an owner/repository. The generated checksum is stored beside the archive and in the ignored package-verification record.

## Limits

A ready reply certifies mechanical prerequisites only. It does not prove factual correctness, complete compliance discovery, a skill defect, a realized cost saving or universal behavior across models/effort settings. Actual output and source review must be evaluated separately from format checks. The ordinary managed investigation retains its existing source-backed review procedure. No user host/model/cache settings, permissions, global hooks, remote repository or publication settings were changed. Private source material, stores, generated answers and release archives are excluded from Git and the distributable package.
