# 0.21.0 candidate — automatic pricing and concise developer readouts

Live Claude validation is deferred at the operator's explicit request until they report that limits have reset. No Claude CLI command or provider invocation was made for this change. Developer distribution remains on hold. The earlier native source-review tests and quota failures remain documented in the [0.20.0 audit](release-audit-0.20.0.md); those are not passes for the new candidate.

## Pricing change

Default engine, CLI and MCP analyses now load and pin a versioned public-rate snapshot automatically. It was verified October 20, 2026 using [Anthropic's official pricing](https://platform.claude.com/docs/en/about-claude/pricing) and exact model IDs on the linked official model pages. The bundled JSON is included in plugin archives, installed-package data and managed-run snapshots. Runtime pricing uses no network or model calls. Explicit operator cards still take precedence; unknown models/modes stay unpriced.

The first line gives estimated source-session token costs for inclusive input/output with cached-input and reasoning portions, without adding either subset twice. Input includes cache creation at the captured TTL. Supported fast, geography and Haiku prompt-length modifiers are applied to the matching response population. A missing reasoning count leaves inclusive output price intact. Analyzer/reviewer usage is excluded. The displayed qualification says these are public API token-price equivalents, not subscription billing. A separately recorded host estimate is retained and an unreconciled difference disclosed, rather than silently replacing an invoice claim or adding two estimates.

Existing pinned cards remain immutable. New price facts are available to old unpriced scopes without changing their saved accounting or authored findings; captured legacy geography is consulted when needed. Prior Claude answers and generated reports remain unchanged. See [pricing behavior and limits](automatic-pricing.md).

## Offline evidence

The opt-in script `scripts/test_offline_pricing.py` was run on the four explicitly supplied logs with subprocess/network connections blocked. The retained run is `.analysis/automatic-pricing/offline-0x9sv0rs`. All captured eligible responses and all four dollar categories were priced. Each selected source's hash and canonical accounting were unchanged. Both prior reviewed Claude answer files checked by hash were unchanged. The audit and cost-only previews remain private; no new Claude findings or answers were manufactured.

The collection session now has an estimated public API token cost of $0.38. This is a newly computed pricing fact, not a newly reviewed Claude answer. The planning session's token estimate differs from its recorded host snapshot; both values and the unresolved billing-scope/freshness distinction are retained. The engine does not label that difference savings or waste.

Synthetic tests cover automatic first-line prices, explicit precedence, pinned-card stability, streaming deduplication, per-request context thresholds, geography/fast multipliers, unsupported modes/IDs, missing/corrupt catalogs, unknown reasoning, retained scopes, separate snapshots and analyzer-cost exclusion. A scoped-tool test simulates metadata-only review with network/subprocesses blocked; it is explicitly not a native Agent quality test. Clean extraction exercises the actual Python CLI's automatic pricing without supplying a rate file. The final full suite discovered 371 tests: **369 passed and two optional private-corpus checks skipped**. Package extraction runs the actual Python CLI on a synthetic known-model log without a price argument; it verifies the computed amount and pinned provenance. See [validation](validation.md).

## Output comparison and remaining gate

The message prepared for Nithin was a combined four-session handoff. The linked native example was a single collection-session answer; it was a different task, and its long selector/file inventory also hurt readability. New writing/reviewer guidance leads with what to change, where and why, keeps the two compliance assessments short, and keeps detailed investigation in internal notes. It aims for 150–250 words without a persistent change, or 250–350 with useful edits, within the existing 450-word hard cap. Exact edits remain conditional on inspected applicable targets. Concision does not permit removing a decision-changing uncertainty or repeating an unsupported historical recommendation.

These style changes have no new live model evaluation. After the operator confirms reset, test the final default native flow against a planning log for a like-for-like comparison, inspect the cost opening and actual recommendations, and retain the raw Agent trace and unedited answer. A pricing preview, unit pass or manually written example is not a substitute. No remote, push, public release or message to developers was made.
