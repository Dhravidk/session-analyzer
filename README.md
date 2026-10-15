# Ally Session Analyzer 0.15.1

## Browse local sessions

Run from a Claude session directory:

```sh
python3 /path/to/ally-session-analyzer/scripts/ally-session.py browse . --detach
```

Or select the native library with `browse ~/.claude/projects --detach`. In Claude Code, invoke `/ally-session-analyzer:browse <directory>`. If Claude is not on PATH, pass `--claude "/path/to/approved/claude"`. The library runs locally on macOS/Linux using Python's standard library; stop the server with the PID returned at launch.

Search saved titles, request previews, session IDs or full paths, then select a session once. Expandable folder groups show the last two directories, with full paths on demand. Each session opens its latest saved analysis, including a labelled partial result; immutable earlier outputs remain internal. An unanalyzed session opens a local metrics/source preview. **Analyze session** and **Update analysis** use the approved Claude workflow with controlled-excerpt approval and a time/money budget. The saved report stays available during an update or after an update fails. Use `--reports <directory>` at launch to admit existing matching runner JSON reports.

Discovery is bounded (three levels, 10,000 parent logs, first and last 1 MiB for native titles/activity and literal request previews). Refresh sessions to discover additional activity. Freshness compares captured payload identities and child-linkage metadata; file stats only invalidate the comparison cache. **Ready** means a completed analysis matches the captured evidence, not that the task succeeded. New activity and incomplete investigation remain separate labels. Missing comparison evidence stays unknown. Pattern masking is incomplete; full retained masked source is included in local reports, with separate controls for model disclosure.


A local analyzer for Claude Code session archives, with deterministic accounting and an approved-Claude investigation workflow. The Python 3.9+ engine uses SQLite and the standard library; it has no model client, network dependency or Jev integration.

The investigation handles **one selected session** and structurally linked, captured children. It preserves the original records, gives Claude compact navigation and measured activity, and lets Claude search, follow evidence links and reread complete visible text. Claude writes the findings and optional recommendations. The renderer preserves that wording; Codex is used for product development and tests only.

Material requirements connect to result evidence, verification scope and known revisions. Recovery episodes retain distinct attempts and deduplicated resource usage. Context/cache and captured-output views help Claude locate evidence without inventing compactions, waste or token attribution. Findings can distinguish adequate instructions that were ignored, an instruction defect, incomplete verification, tool limitations and insufficient evidence. No recommendation is required. New findings include Claude-authored local event explanations and decisive sources. Turn links open the local result; the complete finding retains its answer, sequence, qualifications and optional proposals.

- [Single-session usage and operator checks](docs/single-session-usage.md)
- [Product-manager design and Mermaid diagram](docs/session-analyzer-product-design.md)
- [Governing specification](docs/single-session-investigation-spec.md)
- [Implementation status and limits](docs/implementation-status.md)
- [Validation results](docs/validation.md)
- [Developer usefulness audit and priorities](docs/developer-usefulness-audit-2026-10-15.md)

## Import and measure locally

```sh
python3 -m ally_analyzer --data-dir .analysis/ally run /absolute/path/session.log \
  --namespace ally --output .analysis/reports/accounting.html
python3 -m ally_analyzer --data-dir .analysis/ally sessions ANALYSIS_ID
python3 -m ally_analyzer --data-dir .analysis/ally session-start ANALYSIS_ID SESSION_ID \
  --purpose "Investigate the captured task and useful remaining changes"
python3 -m ally_analyzer --data-dir .analysis/ally session-overview INVESTIGATION_ID
```

Inputs can be ZIP archives, directories, JSONL, or `.log` files containing one JSON object per line. Import/accounting can retain multiple sessions; each investigation selects one root. Existing reports are never overwritten. Use `--help` for all commands; `--data-dir` precedes accounting commands; for `browse`, place it after `browse`.

## Managed Claude investigation and evidence review

The recommended entry point imports the selected session, snapshots the plugin, runs a first Claude investigation and then a fresh Claude evidence review:

```sh
python3 bin/ally-session investigate --source /absolute/path/session.log \
  --work-dir /absolute/path/new-private-run --claude /absolute/path/claude \
  --allow-content --include-source-text-in-report
```

This is packaged with the plugin; run it from the unpacked directory. It uses the approved authenticated Claude CLI and model quota. The default shared cap is $3 and 600 seconds, with 60% reserved for the initial host and the remaining allowance used for review. `--max-budget-usd` and `--timeout` set those total caps. Missing first-stage usage reserves its full allocation rather than treating it as free. A stopped host and its MCP descendants are terminated before proceeding.

The workflow maps all main-session task requests before completion; it does not require reading every assistant step. A voluntary partial finish remains a checkpoint, with at most one additional review continuation inside the original budget. The first finish submission is a saved draft. A separate Claude process rereads primary evidence, reviews causes, recovery, task outcome and missing-evidence claims, and can continue unfinished inquiry. It makes corrections through append-only revisions. Exact quoted evidence must occur in the source and have been delivered during review. Current records and the exact final draft need attributed review checks before finalization. This is model review, not an engine proof of entailment. `partial` remains valid; absent child logs do not by themselves require partial investigation. A completed investigation does not mean the developer's task succeeded.

Each stage's prompt, transcript, answer, budget and usage are preserved. The original and revised text, negative review checks, HTML/JSON, immutable package snapshot and transport audit are retained in the new output directory. No Codex editor or automatic recommendation application runs. The model receives no example-specific answer or source IDs. The older interactive workflow below remains available; it does not automatically launch an independent review process.

## Interactive investigation with approved Claude

Enable controlled excerpts only in the approved environment, and bind the host to the selected investigation:

```sh
ALLY_ANALYZER_HOME="$PWD/.analysis/ally" \
ALLY_ANALYZER_ALLOW_CONTENT=1 \
ALLY_ANALYZER_SESSION_ONLY=1 \
ALLY_ANALYZER_INVESTIGATION_ID=INVESTIGATION_ID \
claude --plugin-dir "$PWD"
```

Then invoke `/ally-session-analyzer:investigate INVESTIGATION_ID`. The workflow loads the shared writing skill. It investigates intent, relevant instructions, apparent successes, failures, alternatives and later recovery. It may finish with findings, no action supported, or insufficient evidence; run completion is a separate state. It does not apply proposed changes.

A bound MCP server rejects legacy endpoints and different investigation IDs. The operator controls artifact admission and execution checks. The plugin cannot restrict unrelated tools exposed by the Claude host; the packaged managed runner supplies a restricted tool allowlist for reproducible demonstrations.

### Metrics and turn patterns

Session totals include user turns, observed LLM calls, requested tool invocations and timestamp span in minutes. Per-turn rows include calls, tools, prompt tokens, cache reads, cache creation, completion tokens, recorded turn duration and observed span. Unknown data remains unknown. Cache tokens are already part of prompt tokens, and thinking is already part of completion.

The turn-pattern figure shows activity groups, counts, median calls/batches, descriptions, shares and separate failure counts. It uses all reconstructed turns in this session as its denominator. The rules and members are inspectable. These are descriptions of recorded activity, not productivity scores or automatic diagnoses of waste.

LLM calls mean reconciled observed responses; unrecorded API retries are unavailable. Tool invocations include requested actions that were denied. Timestamp spans can include idle time and overlapping work. Missing children and ambiguous turn attribution remain explicit.

### Retrieval and recommendations

`get_session_overview` and compact turn pages provide the starting map. Claude can retrieve each turn's events/calls/responses, search the entire admitted visible-text projection, traverse recorded relationships and read selected sources individually or in batches. Every text page has offsets, a fingerprint, omissions and continuation. There is no fixed total reread quota; actual host/user budgets still apply. Original records are retained locally.

Incidents can contain observations without an action. Claims distinguish recorded facts, calculations, participant statements, interpretations and predicted benefits. Registered measurements use explicit scoped identities or a resolved turn/session selection; overlapping selections are non-additive. References and structured quantities are checked mechanically. Causal explanations and claim support remain model judgments.

A recommendation contains its trigger, target, concrete change, tradeoffs and falsifiable verification plan. Missing target evidence or required tests prevents readiness. An operator can admit current target and proposed candidate snapshots into a new scope revision, then run reviewed fixtures bound to the exact proposal and candidate. Model assertions cannot masquerade as machine test results. Ready for review means the stated requirements passed, not proven benefit or permission to apply.

## Read the session report

The opening contains Claude's saved one-to-three-sentence synopsis of intent, recorded work and outcome, followed by open requirements and findings. Requirement rows separate requested work, status and verification evidence. Every turn remains accessible; descriptive finding links and explicit evidence filters help locate relevant work. Saved recovery attempts can be compared directly. Copy remaining work collates saved text, checks, limits and references without inventing an action. The renderer has no model or summarization step.

Full requirement, recovery, token and source details remain behind their controls. Proposed changes appear once. Literal previews retain complete source text when source embedding is enabled. Library HTML exports use the current layout over immutable saved data; original HTML and JSON remain retained.

Nonzero recorded-failure counts open Claude’s saved explanations of what each attempt tried, what failed and what happened next. The original inputs/results and surrounding turn remain accessible. Explanations cite inspected evidence; recovery requires a later successful result and a contextual judgment that it addresses this failure. Unknown causes and missing explanations stay visible. Clicking uses saved analysis and makes no model call. Counts are unchanged by the explanation.

Validation warnings sit beside affected claims. For example, a recognized missing-child count that conflicts with the captured scope is flagged while Claude's original sentence remains unchanged. This is a narrow check, not a general fact-checker.

```sh
python3 -m ally_analyzer --data-dir .analysis/ally export-session INVESTIGATION_ID session.html --include-source-text
```

Source embedding is explicit and follows the same masking policy as model reads. Exporting for a human does not add model read receipts. Without embedding, evidence identifiers remain visible and the report states that text is absent. The Export control downloads HTML, Markdown (.md), or JSON locally. Markdown preserves saved prose, measurements, qualifications and linked source text; JSON retains the full archival payload. The CLI also accepts `export-session … --format md`.

For existing skills and CLAUDE.md, readiness requires inspected current targets, declared scope and overlapping instructions, and an exact edit or invocation. New skills require a reusable procedure and a review of existing coverage. Ignored instructions do not justify appending duplicates. Copy replacement copies only Claude's literal replacement, including intentional newlines; no action applies it automatically. Failed and missing checks remain visible.

## Preserve actual output

Run the shipped workflow on a selected source with your approved Claude executable:

```sh
python3 bin/ally-session investigate \
  --source /absolute/path/session.log \
  --work-dir .analysis/claude-examples/new-run \
  --claude /absolute/path/claude --allow-content --include-source-text-in-report
```

This uses model quota. The output directory must be new. It retains the raw host transcript, exact saved candidates, final answer, HTML/JSON exports and an origin/transport audit, including partial and unsuccessful runs. The default prompt supplies no event or topic anchors. Host usage is separate from source-session usage. An origin audit does not certify semantic quality.

The writing skill requires specific evidence, plain language and concrete remaining actions, and permits no recommendation. It cannot guarantee error-free or “slop-free” output. [Writing criteria](docs/writing-quality.md) and [evaluation protocol](docs/investigation-evaluation.md) describe the remaining quality work. No superiority over `/insights` has been established.

## Package and verification

```sh
python3 -m unittest discover -v
python3 scripts/package_plugin.py
claude --plugin-dir dist/ally-session-analyzer-0.15.1.zip
```

The ZIP includes only allowlisted implementation files, skills and documentation. It excludes private logs, stores, reports, tests and legacy variants. The engine and regression tests run without Claude; opt-in live tests use the operator's authenticated Claude host. CLI plugin loading is tested; permanent desktop installation and other operating systems are not certified.

For another MCP client, use `python3 /absolute/path/scripts/ally-session.py mcp`. The plugin resolves this launcher through `${CLAUDE_PLUGIN_ROOT}`. Existing `analyze`, `explain`, accounting exports, and legacy insight commands remain available outside a bound investigation.

## Local data handling

`ALLY_ANALYZER_HOME` or `--data-dir` selects the store; the default is `~/.ally-session-analyzer`. Original records, cached text and graph indexes remain local. Model access to visible text requires operator-enabled disclosure. Common credential patterns are masked, and thinking, media and environment payloads are omitted with notices. This is incomplete masking, not anonymization. Model-written exports can contain sensitive material even when raw excerpts are not embedded automatically.

New stores and source/database files have owner-only permissions. The engine does not encrypt them. Before a schema upgrade, it backs up the existing database and migrates transactionally; old insight data remains readable under its original contract. There is no automatic retention timer or per-dataset purge. Stop readers before deleting a selected store and remove exported reports separately. Do not import a directory containing the store or distribute private outputs with the plugin.

Import limits are 10,000 files, 2 GiB expanded input, 1 GiB per file and 8 MiB per line. These are protective limits, not demonstrated capacity. Cross-session investigation, native Ally gate adapters, billing reconciliation and independently verified task completion remain outside this release.

## Subagent collection and inspection

Selecting a native session file now also collects `<session-id>/subagents/*.jsonl`, `.log` files and `.meta.json` sidecars beneath its adjacent session directory. A renamed export uses its sole explicit `sessionId`. Collection stays within that directory, rejects links and unsafe identities, and does not search another developer’s machine or an unrelated project. Use `--parent-only` in the CLI or `include_subagents=false` for the import API to disable companion collection. An explicitly selected directory/ZIP remains supported.

Only structurally linked children enter the single-session scope: parent result `agentId` or sidecar `toolUseId`. Nested delegations are followed; unlinked logs are excluded from model access. Capture never proves completeness. A missing child is unavailable, not an agent with zero usage. Parent-reported child rollups are retained separately and never added to observed usage.

The report shows main-agent metrics, turns and source records by default. Click an Agent/Task invocation to inspect its task, parent result, linked child metrics, last captured assistant message, complete paged retained child records and nested invocations. Child failures open their saved explanations and evidence. Main/child combined accounting remains in Coverage. Shared response/tool identities are excluded from individual-agent splits rather than counted twice; combined accounting retains them once. Resumed children share a trace across invocations, and that limitation is visible.

Claude can use `get_subagent_details` with the invocation tool ID to retrieve child metadata and paged source identities, then use the same controlled readers and evidence rules. This API does not fetch new files or grant broader disclosure. The renderer does not generate a child summary or rewrite the child’s last message.

For an Ally integration, supply the selected parent and child logs in this native layout or an equivalent selected bundle, retaining `sessionId`, `agentId`, parent invocation IDs and sidecar metadata. An Ally service would need to fetch those records under its existing access policy before invoking this importer. No Ally backend API is configured or called by this local plugin. The supplied other-developer export has no adjacent child logs; those gaps remain visible.


## Command requests and source explanations

Recognized native command envelopes display a command and argument separately. A path preview shows the filename; expansion retains the whole argument, command, other message text and original masked record. Each copy control copies only its exact saved field. Findings remain linked from the same turn.

Clicking a citation shows its saved Claude explanation. Older reports can reuse an exact-revision review note with its verified quote and attribution. Where neither exists, the report identifies the linked claim and the missing explanation instead of generating one. Ordinary trajectory navigation identifies the record's role and turn. This presentation makes no model call.

## Distribution and current release evidence

The package contains six skills under `skills/`, the MCP configuration and a working `scripts/ally-session.py` launcher. The `bin/ally-session` entry point remains compatible. To validate a clean local installation, unpack the ZIP into a new directory and run:

```sh
claude plugin validate /absolute/path/ally-session-analyzer --strict
claude --plugin-dir /absolute/path/ally-session-analyzer
python3 /absolute/path/ally-session-analyzer/scripts/ally-session.py --help
```

This follows the [Claude Code plugin layout](https://code.claude.com/docs/en/plugins-reference). No marketplace location is configured or claimed. See the [0.13.0 release audit](docs/release-audit-0.13.0.md) for mechanical checks, interrupted Claude checks and the remaining independent evaluation. Earlier outputs and their limitations remain preserved; they are not rewritten by this release.

The runner now stops on terminal setup/API failures instead of starting another reviewer. It preserves the host error and marks the stop external. Fix authentication outside the analyzer, then start a new run directory; failed output is never overwritten.

## PM handoff and release evidence

- [System overview](docs/system-overview.md) and [Mermaid source](docs/session-analyzer-system.mmd).
- [0.11.0 release audit](docs/release-audit-0.11.0.md), including directory browsing and semantic consistency checks.
- [PM slide deck](output/Ally-session-analyzer-PM-0.10.4-reviewed.pptx) (generated local artifact; excluded from Git).
- [Local development and version history](docs/development.md).

Drag the **<|> divider** to resize the source inspector. Its collapse icon hides the panel; **Sources** reopens the selected record with its reading state retained. The chosen proportion is remembered for the browser tab and adapts to available space. Focus the divider and use Left/Right arrows to resize, Home/End for the width limits, or Enter to collapse. Narrow screens use a full-width drawer.

Thinking-only records are labelled **Assistant record · thinking**. Empty, missing, provider-redacted and unsupported content have distinct explanations. Explicit local source exports can include captured masked thinking; model-facing evidence reads continue to omit it. Separate thinking tokens appear only when reported, inside inclusive output usage. Empty excerpts cannot support findings.
