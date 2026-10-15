# Ally Session Analyzer 0.13.1

## Browse local sessions

Run from a Claude session directory:

```sh
python3 /path/to/ally-session-analyzer/scripts/ally-session.py browse . --detach
```

Or select the native library with `browse ~/.claude/projects --detach`. In Claude Code, invoke `/ally-session-analyzer:browse <directory>`. If Claude is not on PATH, pass `--claude "/path/to/approved/claude"`. The library runs locally on macOS/Linux using Python's standard library; stop the server with the PID returned at launch.

Search saved titles, request previews, session IDs or full paths, then select a session once. Expandable folder groups show the last two directories, with full paths on demand. Each session opens its latest saved analysis, including a labelled partial result; immutable earlier outputs remain internal. An unanalyzed session opens a local metrics/source preview. **Analyze session** and **Update analysis** use the approved Claude workflow with controlled-excerpt approval and a time/money budget. The saved report stays available during an update or after an update fails. Use `--reports <directory>` at launch to admit existing matching runner JSON reports.

Discovery is bounded (three levels, 10,000 parent logs, first and last 1 MiB for native titles/activity and literal request previews). Refresh sessions to discover additional activity. Freshness compares captured payload identities and child-linkage metadata; file stats only invalidate the comparison cache. **Ready** means a completed analysis matches the captured evidence, not that the task succeeded. New activity and incomplete investigation remain separate labels. Missing comparison evidence stays unknown. Pattern masking is incomplete; full retained masked source is included in local reports, with separate controls for model disclosure.


Local deterministic accounting and a single-session investigation workflow for an approved Claude host. Requires Python 3.9+ on PATH; no third-party runtime packages or engine model/network client.

```sh
claude --plugin-dir /absolute/path/ally-session-analyzer-0.13.1.zip
```

Use `/ally-session-analyzer:analyze /absolute/path/session.log` to import and measure, `/ally-session-analyzer:explain ANALYSIS_ID` for accounting, or `/ally-session-analyzer:investigate INVESTIGATION_ID` for the scoped investigation. The investigation skill can also select one root from an analysis. Loading the plugin does not collect logs automatically.

The workflow saves an evidence-linked session synopsis and observed outcome, tracks material inquiries and checks source-read prerequisites before completion. It computes session/per-turn calls, tools, tokens and durations and a descriptive turn-pattern table. It keeps original records, supports continued controlled rereading, and records source references, measurements, findings, optional proposals and actual validation states. Expected behavior, no action and insufficient evidence are valid outcomes.

Claude loads the writing skill and authors the report. The renderer formats and escapes saved text without rewriting it. There is no Codex editing stage. All candidate revisions and check failures remain available. Readiness is not proven benefit; the writing skill does not certify accuracy or guarantee an absence of low-quality prose.

The flat document report links turns to findings and proposals, opens retained sources, and copies exact proposed edits without applying them. Existing skills, narrow skill edits, new skills and CLAUDE.md changes are supported only when justified; current-file inspection and scoped overlap review affect readiness. Source text is embedded only when explicitly selected with `export-session --include-source-text` or the model export option under enabled disclosure.

Click a nonzero recorded-failure count in Turn patterns to read Claude’s saved explanation of each attempt: what it tried, what failed and what happened next. Original inputs/results, turn context, evidence limitations and explanation history remain accessible. Explanations are prepared during investigation; the offline report makes no model call. Missing explanations are explicit, and expected or recovered failures remain in the recorded count.

See [usage and operator checks](docs/single-session-usage.md), [design diagram](docs/session-analyzer-product-design.md), [implementation status](docs/implementation-status.md), [validation results](docs/validation.md), and [writing criteria](docs/writing-quality.md).

For model-free use, unpack the ZIP and run:

```sh
python3 -m ally_analyzer run /absolute/path/session.log --output accounting.html
python3 -m ally_analyzer --help
```

Store: `ALLY_ANALYZER_HOME`, CLI `--data-dir`, or `~/.ally-session-analyzer`. Raw records remain local. Controlled text requires operator-enabled `ALLY_ANALYZER_ALLOW_CONTENT=1` in an approved environment. Common secrets are masked; model-facing evidence reads omit thinking, media and environment fields. This is not anonymization. Model prose and source-derived metadata may be sensitive.

Set `ALLY_ANALYZER_INVESTIGATION_ID` to bind the MCP server to one existing investigation and block legacy endpoints; `ALLY_ANALYZER_SESSION_ONLY=1` permits scope selection before binding. Artifact admission and fixture execution are operator CLI actions, unavailable to the model. A temporary fixture directory is not an OS security sandbox. The plugin cannot restrict unrelated filesystem tools in the host.

Existing accounting and legacy reports remain available under their original contracts. Schema migration backs up the previous database. No automatic retention or per-dataset purge exists; stop the processes before deleting the chosen store and remove reports separately. Never distribute the store or logs with this package.

The package excludes private data and legacy variants. CLI loading is integration-tested on the installed macOS Claude host; other hosts and permanent desktop installation remain unverified. No held-out superiority claim over `/insights` or graph-assisted model speedup has been established.

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

The source inspector supports **Expand**, **Restore**, and **Collapse**. Use **Source** in the report header to reopen the selected record with its reading state retained.

Thinking-only records are labelled **Assistant record · thinking**. Empty, missing, provider-redacted and unsupported content have distinct explanations. Explicit local source exports can include captured masked thinking; model-facing evidence reads continue to omit it. Separate thinking tokens appear only when reported, inside inclusive output usage. Empty excerpts cannot support findings.
