# 0.20.0 release candidate — automatic source review

Release gate: **hold developer distribution pending the final-package live default-flow check**. An earlier candidate completed the automatic flow on a real selected log. The planning-log check was interrupted by the approved Claude account's session limit, and the final-candidate launch returned the same HTTP 429 before any work. Neither is a pass. No alternate account, model endpoint or key was used to bypass the limit.

## Changes

The ordinary one-session conversational analysis now saves an immutable draft with `prepare_session_reply`, automatically invokes the packaged native `ally-session-analyzer:source-review` Agent, and retrieves only its accepted standalone answer with `get_reviewed_session_reply`. No second user review prompt is sent. The reviewer inherits the approved host model, uses scoped MCP readers, and has no shell/file-write tools. The design uses [native Claude subagents](https://code.claude.com/docs/en/sub-agents); the actual child context and reads are checked in host traces. Native plugin Agent support was exercised on Claude Code 2.1.299. If unavailable, review remains incomplete rather than silently falling back.

The server requires fresh reads of indexed main requests and structured updates after draft creation, literal source quotes tied to those reads, and two visible authored compliance assessments. Native-host test traces separately verify that a child of the actual packaged Agent launch made the cited reads and accepted submission. MCP itself cannot independently attest caller identity or semantic correctness. Fresh exposure and literal quote matches are prerequisites, not proof of entailment.

Drafts and recorded review attempts are immutable. Schema/argument errors remain visible in the host trace; they are not silently converted into findings. Identical submissions reuse saved progress. The reviewer gets at most two distinct submissions; two rejected submissions return `review_incomplete` rather than another launch instruction. An accepted answer cannot be replaced through that draft. `get_session_reply_draft(include_reviews=true)` exposes retained notes and attempts for audit. The renderer never rewrites Claude findings or recommendations.

Focused follow-ups do not restart a full review. Managed full-report stages retain their existing saved-record/source-review lifecycle; checkpoint/status updates do not create an additional conversational review. General analysis through the analyze/explain skills uses the new default.

## First-line cost

The opening prices **only the analyzed evidence scope**, never analyzer/reviewer usage. Inclusive input cost comprises ordinary input, cache creation at its captured TTL, and reads; cached input is its read subset. Inclusive output includes recorded reasoning priced at the output rate. Only input plus output reconciles to the source total. Separately shown subset costs are not added again.

A pinned matching rate card and complete usage are required for category prices. A recorded host total is never allocated proportionally across categories. Unknown rates, usage or reasoning stay unavailable; partial totals remain labelled subtotals. Tiny known category amounts are displayed without rounding them to zero. Source snapshots retain their final-cost and freshness qualifications. Offline fixtures cover mixed TTLs, unknown reasoning, partial rates, streaming deduplication, linked/unlinked children, and separation from analyzer usage.

Cache/compaction diagnosis and tuning remain on request beyond the opening's required cached-input count/cost. Accounting, captured events, registered queries, readers and resource views remain available.

## Observed native runs

All runs used one generic user prompt, explicitly selected source logs, controlled disclosure, an immutable tested ZIP and the operator's approved local Claude host. No example-specific diagnosis or decisive source IDs were supplied in the prompt. Raw source files, canonical accounting, drafts, reviewed bodies and traces remain local and unchanged.

| Local run | Evidence and result |
| --- | --- |
| `.analysis/claude-developer-reply/run-cj3i33gp` | Real collection log; all 12 checks passed. One actual native reviewer, 18 fresh read request IDs in its child stream, accepted child submission, exact copied opening/body, both compliance assessments, quiet default topics, scoped tools and unchanged source/accounting. |
| `.analysis/claude-developer-reply/run-gkgwbzva` | Real planning log; the native reviewer launched and began rereading, then the host returned HTTP 429, “You've hit your session limit”. No accepted review or final readout; failed, retained. |
| `.analysis/claude-developer-reply/run-etnn2vx1` | Later candidate with the final review-history/cap behavior and clarified guide scope. HTTP 429 at startup; no reviewer launch or source work. Failed, retained. |

The successful collection review corrected material draft claims before delivery: it checked the queued human update's parent chain, removed an unsupported probability of incompleteness, and described the file/worktree search as references rather than proof that matching sessions produced an artifact. Its ending keeps delivery unverified because the copy command has no captured result. No permanent skill edit was justified from that session. The unedited answer and internal notes are in that run's `answer.md` and store.

The earlier preliminary run `run-h0h5v6kd` is also retained with its original audit. Its wording prompted the general guidance to distinguish a command's stated purpose from its actual selectors/results. The stronger successful run above used that guidance. The final package also clarifies full-report versus conversational scope, exposes retained review history, preserves invalid source attempts, and stops after two failed submissions. Those final changes have offline coverage; the account limit prevented completing the final-package native check. Do not present the earlier tested ZIP as byte-identical to the final candidate.

## Local checks and next gate

The final offline suite discovered 359 tests: **357 passed and two optional private-corpus checks skipped**. The clean-extraction package check is part of that suite. Native manifest validation and the pending live gate are recorded in the [validation log](validation.md). Raw developer logs, stores, traces, generated answers, credentials and release ZIPs are excluded from Git and the distributable. The package builder now includes the reviewer agent, including in managed-run immutable snapshots.

After the approved account is available, rerun the default flow against the final candidate source without supplying an expected answer:

```sh
python3 scripts/test_claude_developer_reply.py \
  --source /absolute/path/to/the/selected/session.jsonl \
  --allow-content --claude /absolute/path/to/approved/claude \
  --effort high --max-budget-usd 3 --timeout 600
```

Require all 12 checks, inspect the actual source-backed judgments, compare final runtime/agent/skill bytes with that tested immutable package, then clear the distribution hold. The check must run through the normal native Agent path in one user turn. A separate manual review prompt is not a substitute. Do not count a quota error, interrupted reviewer, formatting pass or saved review as a semantic-quality guarantee. No public release, push or message to developers occurred.
