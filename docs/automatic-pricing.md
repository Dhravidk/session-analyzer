# Automatic verified pricing

Default analyses load the bundled `ally_analyzer/verified_prices.json` snapshot without a model call, API key, runtime web request or separately supplied price file. Rates were verified on October 20, 2026 against [Anthropic's pricing table](https://platform.claude.com/docs/en/about-claude/pricing) and the official model pages linked in the snapshot. The analysis pins the entire card, its source metadata and content hash. Updating the bundled catalog does not silently change a previously pinned card.

The snapshot covers exact Claude API IDs for Opus 5.5, Sonnet 5.5, Haiku 5.5, Fable 5.1, Opus 5, Sonnet 5, Opus 4.6, Sonnet 4.6, and Haiku 4.5 (its alias and documented dated ID). It includes the supported Opus fast-mode multiplier, US-only inference pricing, and Haiku 5.5's per-prompt threshold counting all input categories. Unknown IDs, missing usage/TTL data or unsupported billing modes remain unpriced. There is no family-name approximation or assumed zero cost.

The first line shows only the total estimated source-session cost, for example `Estimated session cost: $2.26.` Incomplete pricing remains a labelled subtotal and unavailable cost stays unavailable. Material missing-capture and snapshot-freshness limits remain visible. Recommendations, concise task/compliance assessments and evidence follow; the initial answer does not add token/component breakdowns or routine pricing and reconciliation notes.

For a follow-up such as `/analyze how was the cost calculated?`, `get_session_overview` retains `session_readout.token_summary`, all four token/dollar components in `usage`, routine notes in `cost_details_on_request`, and the complete `source_cost`. Collection readouts expose the same fields, including the shared-response reconciliation note, and per-session details remain accessible. These queries do not require a new full review or edit any saved answer.

These are **public API token-price equivalents**, not subscription charges or invoices. The retained notes include the verification date and any unreconciled separate host estimate, available on request. They do not establish historical invoice rates, cloud-region/private discounts or non-token fees. A host estimate is never added to the token estimate or allocated across its categories. Analyzer/reviewer usage is outside the imported evidence scope and excluded from the total.

Input includes ordinary tokens, creation at its recorded TTL and reads. Cached input is already inside input; reasoning is already inside output. Only inclusive input plus inclusive output adds to the estimate. Missing reasoning does not erase a known inclusive output price. Small known component costs remain inspectable instead of rounding to zero. Changing the initial display does not change accounting, rate selection, resource tools or historical Claude-authored output. Saved drafts keep their original cost presentation when resumed, and accepted replies are returned verbatim.

An explicit `--prices` file or MCP `price_book` remains authoritative and is not merged with guessed default rates. This supports operator-specific pricing. Older unpriced scopes can query newly computed price facts using the verified snapshot; their saved configuration, source accounting, findings and accepted Claude answers remain unchanged. Legacy geography metadata is checked against captured usage rather than silently assuming a US-only response was global. Previously generated files are not rewritten.

To update automatic prices, verify official sources, publish a new dated snapshot/version, and update calculation and package tests. The verification date is a snapshot date, not a claim that the provider's historical price started that day. Keep unknown model/mode coverage explicit. Restoring a missing/corrupt bundled resource or supplying a valid explicit card is required; a broken install does not trigger an unverified network fallback.

For a local check on an explicitly selected log, without Claude:

```sh
python3 scripts/test_offline_pricing.py \
  --source /absolute/path/session.jsonl --require-priced \
  --preserve-output /absolute/path/prior-claude-answer.md
```

The script blocks subprocesses and network connections, retains private previews/audits under `.analysis/automatic-pricing/`, and checks the selected source, canonical accounting and prior output hashes. It exports computed cost facts only. It does not author a new Claude investigation, certify existing findings, or replace the pending live default-flow/style test.
