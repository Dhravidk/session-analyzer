# 0.18.0 release evidence

October 20, 2026. This release changes the default developer readout and preserves the existing resource-analysis tools. It does not establish complete diagnostic accuracy.

The opening is computed from scoped accounting, for example on the labelled synthetic session:

> You spent approximately $12.34 (180 input tokens, including 90 cached input tokens; 120 output tokens, including 36 reasoning tokens) on this session.

The amount is a synthetic host estimate, not a real developer invoice. Missing costs/counts and partial pricing have explicit alternate wording. Cached input stays within input; reasoning stays within output. The population is the main agent and structurally linked captured children, with reconciled identities counted once. Analyzer cost is separate.

`prepare_session_reply` validates a new Claude-authored body before a general reply. It flags common unrequested resource-detail wording and repeated openings, or returns the computed opening, material qualifications and the unchanged body to copy. Explicit resource detail requires the quoted current request and selected topics. Application cache paths such as `cache.py` are not automatically resource-tuning violations. This is a bounded mechanical wording check; it cannot establish factual correctness, interpret every synonym or guarantee that every model invokes/copies it. No global Stop hook or automatic redaction was added. Existing tools, raw evidence, saved judgments and requested follow-ups remain available.

## Mechanical checks

- Full standard-library suite: 329 discovered, 327 passed, two optional private-corpus skips.
- Twelve new tests exercise the readout/preflight, underlying cached-input and compaction queries, scope/disclosure controls and preserved prose.
- Existing isolated-package checks exercise startup and tool discovery outside the checkout.
- Runtime Python/assets, manifests and skills match the retained successful Claude-test ZIP byte for byte; release documentation changed afterward.

## Actual Claude exercise

`scripts/test_claude_readout.py` runs two prompts on a clearly synthetic session in the approved local CLI. Default cap: $2 and 360 seconds. It preserves prompts, the immutable tested package, all answers, raw traces, rejected calls and checks under `.analysis/claude-readout/`; these generated artifacts are not shipped or committed.

The host reported Claude Code 2.1.299 and `claude-sonnet-5-5`. No private developer sessions were supplied. Local artifacts:

- `run-rgxle5jd`: first trial. Correct opening and requested follow-up; unsolicited default resource detail and one rejected bare tool alias.
- `run-57rcc5fp`: stricter prompt-only guidance. Correct opening/follow-up; default resource detail still leaked and one placeholder tool call was rejected.
- `run-uh1ret84`: preflight-enabled trial. All eight original checks passed. An additional offline check in `copy-verification.json` confirms the final reply equals the ready preflight text, apart from surrounding whitespace. No rejected unknown-tool call occurred in this trial.

The successful first reply began with the exact computed cost/token sentence and did not discuss caching/compaction outside it. The second reply used the timeline and registered query to explain 90 cached-input tokens out of 180 (50%), one manual boundary, 100 ms recorded duration and separate pre/post metadata of 200/50 tokens. The normalized accounting hash stayed unchanged. Executed-tool policy remained enforced. Per-stage host cost snapshots remain in the local audits; resumed telemetry may be cumulative and is not added into the analyzed session's amount.

## Limits and review

These checks concern format, accounting and tool use for one authored case, not held-out recommendation quality. The successful answer still suggested adding an authorization rule despite the adequate captured instruction and admitted missing target evidence. The preflight did not certify or repair that reasoning. Earlier answers and failed attempts remain unedited. A broad quality claim, measured cost reduction, consistent compliance across models, or superiority over `/insights` is not established.

The release is a private developer ZIP. No marketplace publication, remote push or delivery to other people is performed by packaging it.
