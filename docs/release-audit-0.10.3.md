# Release audit — 0.10.3

This is a locally tested Claude Code plugin distribution candidate. The package structure and local engine work; a fresh model-level check of the new citation explanation field is still blocked by expired Claude OAuth. This is not a claim of production readiness across Ally environments or superiority over `/insights`.

## Changes audited

- Selected command-row design implemented with Findings retained. Recognized wrappers become literal command/argument fields; full values and the original masked source remain accessible. Ambiguous wrappers remain literal.
- Citation explanations are authored by Claude. Older reports reuse only a matching current-owner review note and verified source quote. Missing explanations are explicit. Requirement, verification, recovery-attempt and attribution links also carry their exact saved claim context. The renderer does not manufacture a summary or edit saved findings.
- Source navigation preserves the clicked control through desktop reflow and returns focus on narrow-screen exit. All token categories, failures, child drill-downs, coverage and copy/export controls remain.
- The MCP launcher now lives in `scripts/ally-session.py`; all five skills remain standard Markdown files. The archive builder has a real `--help` and explicit destination option, reproducible bytes and an allowlist. `bin/ally-session` remains compatible.
- Terminal API/authentication errors stop the managed runner before another review is attempted. The real host message remains saved, with a failed external stop rather than an investigator-choice explanation.

## Backend and package checks

| Check | Observed result | Scope |
| --- | --- | --- |
| First full regression pass | 202 tests passed in 21.747 s | Both optional supplied corpora enabled. |
| Second full regression pass | 204 tests passed in 21.046 s | Includes clean-package and terminal-authentication regressions. |
| Final pass after citation-context fix | 204 tests passed in 21.892 s | Both supplied corpora; exact linked-context and unchanged-payload assertions added to the existing regression. |
| JavaScript syntax | Passed | Bundled Node runtime checked the renderer. |
| Claude manifest validation | Passed with `--strict` | Installed Claude Code 2.1.295; advice about a future marketplace line only. No marketplace is claimed. |
| Clean archive extraction | Passed | Python `-I`, unrelated working directory, path containing spaces, MCP handshake and tools, disclosure off. |
| Archive repeatability | Passed | Two builds from the same files have equal SHA-256. Private logs/stores, tests, reports and legacy variants excluded. |
| Actual plugin loader | Connected | All five skills and the MCP server loaded in Claude 2.1.295. A model request then failed authentication. |

The regression suite covers parsing, identity reconciliation, masking/disclosure, paged rereading, scope escapes, import limits, migrations, metrics, missing/shared child identities, requirement revisions, stale/narrow verification, expected failure and correct denial, episode unions, cache drops without compaction, attribution versions, proposal readiness and immutable review. These are defined assertions over fixtures and observed input formats, not proof of correct interpretation on every session.

The new package test initially used the wrong reader tool name; correcting that test expectation produced a passing real handshake. Browser assertions that compared JSON serialization order were replaced with deep value equality. Early position checks using locator clicks also included the automation's own recentering; native activation is the relevant check. A locator-driven replacement-copy check also returned a stale clipboard value despite the success notice. Native button activation was then checked against the complete saved replacement and invocation; both matched exactly, including the replacement's final newline. These test-harness observations remain recorded and were not changes to Claude's output.

## Browser checks

The first pass exercised the actual supplied-log report, API-saved synthetic boundary cases and earlier untouched Claude-authored synthetic reports. A second pass repeated the changed source interactions and core report flows after fixes. Evidence is in `.analysis/audit-0.10.3/` and `design-qa.md`.

| Area | Cases checked |
| --- | --- |
| Turn rows | No-argument command, full path argument, exact copy, original envelope, long request, all 32 turns, multiple findings. |
| Source inspector | Saved review reason and quote, absent reason, paired input/result, plain text, full large result, wrap, exact copy, previous/next, surrounding context, return to finding/failure. |
| Requirements/recovery | Saved narrower-scope and stale-revision qualifications, exact claim context, same-goal attempt rationale and return to finding; no fabricated explanation for legacy citations. |
| Resources | Main input total/uncached/write/read/output; missing child unknown usage; combined captured totals; analyzer usage separately labelled; per-turn duration versus span. |
| Children | Parent-first view, captured child, nested invocation, missing child, retained parent results, child failures. |
| Recommendations | Exact replacement including quotes, literal shell-looking text, tags, Unicode and trailing newline; exact invocation; admitted target source. Mechanical synthetic examples, not Claude quality evidence. |
| Empty states | No justified action, insufficient evidence, incomplete investigation, not run and findings without proposals remain distinct. |
| Exports | JSON deep-equal to the saved report; HTML reopens with working controls and no duplicated transient inspector. |
| Responsive/keyboard | 1586×992 desktop and 390×844 narrow view; no document overflow; table retains Findings through horizontal scrolling; source becomes modal; Escape restores focus. |

The browser observed a 38,200-character retained result with 627 lines. Full-result access and exact copy preserved the entire string; display gutters replaced saved line prefixes only in presentation. The supplied report timeline advanced from 30 to 60 of 839 records. Native source activation retained the clicked control within 0.16 px after reflow. These are observations for those records and viewports, not universal performance guarantees.

## Actual Claude evidence and the current blocker

Earlier guided development runs remain intact: `synthetic-evidence-0.10.0` identified narrowed verification and a later unchecked revision with a missing verifier trace; `synthetic-recovery-0.10.1` preserved an expected/recovered failure with measured episode resources; `synthetic-response-0.10.2` distinguished a delivered text answer from an unsupported test-pass claim. Each completed its declared inquiry with no recommendation. Their exact saved wording and negative/intermediate checks remain unchanged.

The supplied-log report still uses its completed 0.8.1 investigation: 32 main requests, 2 active findings, 6 active failure explanations and no recommendations. Its 16 child traces were absent from the supplied export. Rendering that output in 0.10.3 is not a new investigation and does not retrofit requirement maps or episodes.

The first 0.10.3 attempt could not locate `claude`. The executable was then found inside the installed desktop app. It loaded the plugin and connected MCP, but returned `Failed to authenticate: OAuth session expired and could not be refreshed`, with no analysis calls or model-token usage. CLI `auth status` had reported logged-in; that was insufficient evidence of a working model connection. The failed run is retained under `source-explanations-0.10.3-attempt2`. The original runner repeated the failure in review; the new regression verifies that version 4 stops after the first terminal error. Sign-in requires completion of a browser verification step by the operator.

A small isolated CSV repair project is prepared at `.analysis/audit-0.10.3/claude-created-session/` for the requested newly generated realistic Claude Code session. It contains synthetic tests for ASCII, quotes/commas and Unicode/line breaks. No fresh Claude execution is claimed while sign-in remains blocked. Existing model-authored examples and deterministic fixtures cover the locally testable behavior meanwhile.

## Remaining work, in priority order

1. **Finish the new live citation check after sign-in.** Verify that Claude writes useful source-specific sentences, that review rejects unsupported ones and that long-source rereads still work. A passing schema is insufficient.
2. **Run the independent usefulness study.** Label unseen sessions before inspection, blind the report comparison and measure unsupported claims, missed material requirements, evidence-navigation time and justified-action usefulness. Keep zero-action reports in the sample. Do not optimize toward recommendation count.
3. **Add operator-controlled resume for costly interrupted investigations.** The existing workflow has a bounded continuation; a later separate invocation currently starts a new work directory. Resume should bind the original evidence and plugin versions, preserve previous stages and record any scope revision. Validate against a fresh run before relying on it.
4. **Add a reviewable export-disclosure manifest before broad sharing.** Current masking is incomplete and export opt-in is explicit. A preview of included source categories, paths and artifacts would let the operator remove selected content without altering the retained local evidence or pretending the export is complete.
5. **Validate target environments and update behavior.** Python availability, installation/update/uninstall, file permissions and native report opening should be exercised on the intended Ally laptop and approved Claude host. Current macOS local validation is not Windows/Linux certification.

Ally access is needed for compatibility, not for the implemented local mechanics. Obtain representative versioned parent/child exports and linkage, historically loaded instructions with scope/precedence, task-specific artifact revisions, disclosure requirements and the verified authentication/endpoint/deployment contract with test access. Fetch future Jira/PR/CI artifacts only for an actual task and material gap. Cross-session analysis, active-time decomposition, concurrency savings and critical paths remain deferred.

## PM handoff

The 11-slide editable PowerPoint is `output/Ally-session-analyzer-PM-0.10.3-reviewed.pptx`. It contains the actual report, system flow, product boundaries, observed model examples, audit results and deferred Ally evidence. All 11 slides were rendered from the final PPTX and visually inspected. A wrapped caption overlap and reversed diagram arrows were corrected before final handoff. Structural package, geometry/font, native-table and first-party import checks passed; native PowerPoint rendering is not certified. Receipt: `.analysis/pm-deck-0.10.3/validation-reviewed.json`.
