# Automatic verified pricing

Default analyses load the bundled `ally_analyzer/verified_prices.json` snapshot without a model call, API key, runtime web request or separately supplied price file. Rates were verified on October 20, 2026 against [Anthropic's pricing table](https://platform.claude.com/docs/en/about-claude/pricing) and the official model pages linked in the snapshot. The analysis pins the entire card, its source metadata and content hash. Updating the bundled catalog does not silently change a previously pinned card.

The snapshot covers exact Claude API IDs for Opus 5.5, Sonnet 5.5, Haiku 5.5, Fable 5.1, Opus 5, Sonnet 5, Opus 4.6, Sonnet 4.6, and Haiku 4.5 (its alias and documented dated ID). It includes the supported Opus fast-mode multiplier, US-only inference pricing, and Haiku 5.5's per-prompt threshold counting all input categories. Unknown IDs, missing usage/TTL data or unsupported billing modes remain unpriced. There is no family-name approximation or assumed zero cost.

The first line shows the estimated cost and token/dollar amounts for input, cached input, output and separately reported reasoning. Input includes ordinary tokens, cache creation at its recorded TTL and cache reads. Cached input is the read portion already inside input; reasoning is already inside output. Only inclusive input plus inclusive output adds to the estimated total. Missing reasoning does not erase a known inclusive output price. Small known costs remain visible instead of rounding to zero.

These are **public API token-price equivalents**, not subscription charges or invoices. The displayed qualification retains the verification date. It does not establish historical invoice rates, cloud-region/private discounts or non-token fees. A separate recorded host estimate is never added to the token estimate or allocated across its categories; an unreconciled difference is disclosed. Analyzer/reviewer usage is outside the imported evidence scope and excluded from the first line.

An explicit `--prices` file or MCP `price_book` remains authoritative and is not merged with guessed default rates. This supports operator-specific pricing. Older unpriced scopes can query newly computed price facts using the verified snapshot; their saved configuration, source accounting, findings and accepted Claude answers remain unchanged. Legacy geography metadata is checked against captured usage rather than silently assuming a US-only response was global. Previously generated files are not rewritten.

To update automatic prices, verify official sources, publish a new dated snapshot/version, and update calculation and package tests. The verification date is a snapshot date, not a claim that the provider's historical price started that day. Keep unknown model/mode coverage explicit. Restoring a missing/corrupt bundled resource or supplying a valid explicit card is required; a broken install does not trigger an unverified network fallback.

For a local check on an explicitly selected log, without Claude:

```sh
python3 scripts/test_offline_pricing.py \
  --source /absolute/path/session.jsonl --require-priced \
  --preserve-output /absolute/path/prior-claude-answer.md
```

The script blocks subprocesses and network connections, retains private previews/audits under `.analysis/automatic-pricing/`, and checks the selected source, canonical accounting and prior output hashes. It exports computed cost facts only. It does not author a new Claude investigation, certify existing findings, or replace the pending live default-flow/style test.
