# Single-session investigation: use and operator checks

Version 0.10.2. Start with one captured task and preserve the resulting report, including uncertainty and unsuccessful proposals. The [product design](session-analyzer-product-design.md) explains the workflow; the [specification](single-session-investigation-spec.md) defines its contract.

## Managed Claude investigation and evidence review

The recommended entry point imports the selected session, snapshots the plugin, runs a first Claude investigation and then a fresh Claude evidence review:

```sh
python3 bin/ally-session investigate --source /absolute/path/session.log \
  --work-dir /absolute/path/new-private-run --claude /absolute/path/claude \
  --allow-content --include-source-text-in-report
```

This is packaged with the plugin; run it from the unpacked directory. It uses the approved authenticated Claude CLI and model quota. The default shared cap is $3 and 600 seconds, with 60% reserved for the initial host and the remaining allowance used for review. `--max-budget-usd` and `--timeout` set those total caps. Missing first-stage usage reserves its full allocation rather than treating it as free. A stopped host and its MCP descendants are terminated before proceeding.

The workflow reads all main-session user requests and saves a scoped requirement-to-result map before completion; it does not require reading every assistant step. A voluntary partial finish remains a checkpoint, with at most one additional review continuation inside the original budget. The first finish submission is a saved draft. A separate Claude process rereads primary evidence, reviews causes, recovery, task outcome and missing-evidence claims, and can continue unfinished inquiry. It makes corrections through append-only revisions. Exact quoted evidence must occur in the source and have been delivered during review. Current records and the exact final draft need attributed review checks before finalization. This is model review, not an engine proof of entailment. `partial` remains valid; absent child logs do not by themselves require partial investigation. A completed investigation does not mean the developer's task succeeded.

Each stage's prompt, transcript, answer, budget and usage are preserved. The original and revised text, negative review checks, HTML/JSON, immutable package snapshot and transport audit are retained in the new output directory. No Codex editor or automatic recommendation application runs. The model receives no example-specific answer or source IDs. The older interactive workflow below remains available; it does not automatically launch an independent review process.

## Optional local instruction/artifact snapshots

Add `--artifact-manifest /absolute/path/artifacts.json` to the managed command. This uses the same operator admission as the interactive flow:

```json
[
  {"path":"historical-skill.md","label":"Selected historical skill","temporal_relation":"historical","completeness":"complete","version":"1.0"},
  {"path":"CLAUDE.md","label":"Current project instructions","temporal_relation":"current","completeness":"complete"}
]
```

Paths may be absolute or relative to the manifest. Select only files relevant to the session and its material evidence gaps. Historical provenance is your declaration; a current file does not prove what ran. This local interface does not establish compatibility with Ally, Jira or CI.

For a clearly synthetic diagnostic exercise, run `python3 scripts/create_diagnostic_fixture.py /absolute/path/fixture` and pass the printed source/manifest paths to the managed workflow. The fixture is an authored regression case, not a held-out quality benchmark.

## Interactive start and bind

```sh
python3 -m ally_analyzer --data-dir .analysis/ally run /absolute/path/session.log --output accounting.html
python3 -m ally_analyzer --data-dir .analysis/ally sessions ANALYSIS_ID
python3 -m ally_analyzer --data-dir .analysis/ally session-start ANALYSIS_ID SESSION_ID \
  --purpose "Investigate the captured task, outcome and useful remaining changes"
```

Use the returned investigation ID. It pins the session, admitted children, source hashes, adapter, graph, text and disclosure versions. A named child with no imported trace is a gap, not a source that can be reconstructed from its parent's summary.

```sh
ALLY_ANALYZER_HOME="$PWD/.analysis/ally" \
ALLY_ANALYZER_ALLOW_CONTENT=1 \
ALLY_ANALYZER_SESSION_ONLY=1 \
ALLY_ANALYZER_INVESTIGATION_ID=INVESTIGATION_ID \
claude --plugin-dir /absolute/path/ally-session-analyzer-0.10.2.zip
```

Invoke `/ally-session-analyzer:investigate INVESTIGATION_ID`. Controlled text access is for the approved environment. Without the content flag, metric/navigation queries work but text reads and searches fail explicitly. The bound analyzer rejects other investigations and legacy APIs. The host may expose unrelated tools; use a restricted host configuration when enforcing access beyond this plugin.

The workflow loads `write-report`, maps requests and outcomes, tracks material questions with `save_inquiry`, investigates original results, saves exact claims and optional recommendations, then freezes its conclusion. Claude can finish a completed inquiry with insufficient evidence. A partial run means the declared inquiry was not finished; it does not mean a supported problem was found.

## Navigation without discarding evidence

| Tool | Use and bounds |
| --- | --- |
| `get_session_overview` | Session metrics, compact turn patterns, request/ending landmarks, capture gaps and admitted artifacts. |
| `get_investigation_records` | Page events, compact turns, responses, tools, incidents, claims, measurements, proposals, access or capture diagnostics. Defaults to 20, maximum 200 records; oversized pages shrink without truncating member records. |
| `get_investigation_records` with `turn_id` | Retrieve all event, response or tool identities belonging to a particular turn through ordinary pagination. |
| `read_investigation_batch` | Read up to eight selected sources; defaults to 2,000 characters each, maximum 3,000. Every page has its own continuation. |
| `read_investigation_evidence` | Read one source from a character offset, 8,000 characters by default and 12,000 maximum. Continue with the returned fingerprint and offset. |
| `search_investigation_text` | Literal, case-insensitive search; first match per source, with snippets. Defaults to 1,000 scanned sources/10 matches, maximum 5,000/50. Follow the scan cursor with the same query. |
| `get_related_evidence` | Bounded parent, order, response, call/result and delegation navigation. Depth 1–6; page size at most 100. Follow returned nodes if expansion is incomplete. |

An empty partial search is not evidence of absence. Graph order does not imply causality. Text pages are exact masked projections, not model summaries; original source bytes remain local. Projection versions are pinned so parser upgrades do not change existing citation offsets. Omitted thinking, media and environment content is stated explicitly. The access record measures delivered text, not understanding.

For local inspection, put tool arguments in a JSON file, then use:

```sh
python3 -m ally_analyzer --data-dir .analysis/ally session-call \
  get_investigation_records arguments.json
python3 -m ally_analyzer --data-dir .analysis/ally session-call \
  read_investigation_evidence arguments.json --allow-content
```

The exact argument schemas are returned by MCP `tools/list` and defined in the packaged `ally_analyzer/session_contract.py`.

## Measurements and interpretation

Session and per-turn counts use reconciled response/call identities. Streaming fragments and duplicate exports do not inflate them. Calls denied execution remain requested invocations. User-turn origins and ambiguous attribution are explicit. Prompt tokens include cache reads and writes; completion includes reported thinking. Recorded duration and timestamp span are separate measurements. A 20-minute span does not establish 20 minutes of avoidable work.

For an incident, `measure_selection` accepts explicit IDs, a `turn_id`, or `all_scoped: true`, plus the membership rationale. These alternatives cannot be mixed. Formulas cover counts, token categories, recorded tool duration, an ordered two-event interval and an explicit tool-opportunity rate. Resolved identity counts and selection hashes make grouping inspectable. Unknown totals carry known subtotals and coverage. Overlapping incident values cannot be summed; use union identities.

The turn-pattern figure groups all reconstructed turns, including those without a recorded response. Each row contains its count, median LLM calls/batches, definition, share and separate failure counts. Rules are ordered and mutually exclusive. Shares describe turns within this session, not time, tokens, task value or team prevalence.

## Admit a target and candidate

The model cannot read a path from archived text or admit a file itself. An operator selects the actual file:

```sh
python3 -m ally_analyzer --data-dir .analysis/ally admit-artifact /selected/target.py \
  --label "Current verification gate" --temporal-relation current --completeness complete --version REVISION
python3 -m ally_analyzer --data-dir .analysis/ally admit-artifact /selected/candidate.py \
  --label "Proposed verification gate" --temporal-relation proposed --completeness complete --version CANDIDATE
python3 -m ally_analyzer --data-dir .analysis/ally revise-scope INVESTIGATION_ID \
  --artifact-id TARGET_SNAPSHOT_ID --artifact-id CANDIDATE_SNAPSHOT_ID
```

This creates a new linked investigation. It does not modify the previous scope or transfer claim validity and tests. Rebind the host to the new ID. Claude reads the selected target, submits a proposal naming both snapshot IDs, and records its contextual review. A current file does not prove what existed during the original session; use historical snapshots only when their origin supports that label. Partial target snapshots cannot satisfy full-target inspection.

## Execute prepared checks

Only the operator CLI runs checks. Review the candidate, fixture code and plan first; these are executable local programs. The runner uses fresh temporary fixture copies, not an OS security sandbox. It never automatically replays commands from the analyzed session.

The plan has `version`, an operator `environment` description, a single `candidate_filename`, and `checks`. Each check uses an explicit argument vector with `{candidate}`, an expected exit code, and optional literal stdout/stderr assertions, stdin and a 1–60 second timeout. For example, a prepared verifier fixture can use:

```json
{
  "version": "gate-fixtures-v1",
  "environment": "Python verifier; reviewed fixtures for this target revision",
  "candidate_filename": "gate.py",
  "checks": [
    {"check_type": "syntax_or_schema", "argv": ["python3", "check_syntax.py", "{candidate}"], "expected_exit": 0},
    {"check_type": "positive_behavior", "argv": ["python3", "check_rejects_broken.py", "{candidate}"], "expected_exit": 0},
    {"check_type": "negative_behavior", "argv": ["python3", "check_accepts_valid.py", "{candidate}"], "expected_exit": 0}
  ]
}
```

These filenames describe files the operator prepares; they are not bundled generic validators. Choose checks that exercise the actual target and meaningful counterexamples. Hooks/configuration also require a `target_contract` check against the relevant schema and trigger semantics. A generic matcher fixture does not certify native Claude hook compatibility.

```sh
python3 -m ally_analyzer --data-dir .analysis/ally fixture-check NEW_INVESTIGATION_ID RECOMMENDATION_ID \
  --fixture-dir /selected/reviewed-fixtures --plan /selected/plan.json
```

Results bind the exact scope, proposal, target, candidate, fixture, plan and executable fingerprints. Each check records exit, output hashes, elapsed time and status. Missing runtimes are unavailable, not executed successes. Truncated output, changed candidate bytes, timeouts or assertion failures prevent passing. Tests on a previous proposal do not transfer to its revision. Failure history is retained; later successes cannot silently erase it.

A non-executable prompt/skill/workflow change uses its applicable evidence and contextual review requirements. A model review is explicitly attributed to the model; it is not an independent execution attestation. `ready_for_review` means the declared policy requirements passed, not that the change improves future sessions.

## Export and record follow-up

```sh
python3 -m ally_analyzer --data-dir .analysis/ally export-session INVESTIGATION_ID investigation.html --include-source-text
python3 -m ally_analyzer --data-dir .analysis/ally export-session INVESTIGATION_ID investigation.json --format json
python3 -m ally_analyzer --data-dir .analysis/ally review-recommendation INVESTIGATION_ID RECOMMENDATION_ID \
  --status needs_evidence --note "Need the relevant target revision before accepting this change."
```

Exports include all saved candidates, including failed, superseded and withdrawn revisions. Choose a new filename each time. Reviews are append-only operator reports, independent of readiness; a tested-beneficial note is not independent certification. No review automatically applies a change or trains a model.

The HTML Export menu downloads the saved data as HTML or JSON. Source embedding is optional, disabled by default, and never increments Claude's evidence-access ledger. A text-free export preserves source identities and visibly identifies that limitation.

## Explaining counted failures

The investigation calls `get_recorded_failures` to obtain paged identities and context pointers for the exact counted attempts. Claude reads selected original evidence, follows relevant recovery, and saves a `save_failure_explanation` record per attempt. Each record contains its summary, follow-up, resolution, references, limitations and model provenance. An explained attempt must cite its own input and result; cited ranges must have been delivered. When later results are available, an explained attempt also needs an inspected and cited later input/result pair. Discovery returns the next two pairs as navigation aids, not inferred retries. Partial evidence and unknown recovery require an explicit limit. Recovery requires an inspected later successful tool result; the contextual relationship remains a model judgment.

A changed explanation is an append-only revision for the same invocation. Frozen runs remain immutable. Older reports without explanations display that gap; renderers never fabricate a fallback diagnosis or rewrite existing output. No explanation creates or applies a recommendation. The modal keeps original input/result navigation, turn links and saved evidence checks. Coverage distinguishes explained, insufficient evidence and not investigated attempts. Completion still describes the declared investigation, not exhaustive session coverage.

## Subagent collection and inspection

Selecting a native session file now also collects `<session-id>/subagents/*.jsonl`, `.log` files and `.meta.json` sidecars beneath its adjacent session directory. A renamed export uses its sole explicit `sessionId`. Collection stays within that directory, rejects links and unsafe identities, and does not search another developer’s machine or an unrelated project. Use `--parent-only` in the CLI or `include_subagents=false` for the import API to disable companion collection. An explicitly selected directory/ZIP remains supported.

Only structurally linked children enter the single-session scope: parent result `agentId` or sidecar `toolUseId`. Nested delegations are followed; unlinked logs are excluded from model access. Capture never proves completeness. A missing child is unavailable, not an agent with zero usage. Parent-reported child rollups are retained separately and never added to observed usage.

The report shows main-agent metrics, turns and source records by default. Click an Agent/Task invocation to inspect its task, parent result, linked child metrics, last captured assistant message, complete paged retained child records and nested invocations. Child failures open their saved explanations and evidence. Main/child combined accounting remains in Coverage. Shared response/tool identities are excluded from individual-agent splits rather than counted twice; combined accounting retains them once. Resumed children share a trace across invocations, and that limitation is visible.

Claude can use `get_subagent_details` with the invocation tool ID to retrieve child metadata and paged source identities, then use the same controlled readers and evidence rules. This API does not fetch new files or grant broader disclosure. The renderer does not generate a child summary or rewrite the child’s last message.

For an Ally integration, supply the selected parent and child logs in this native layout or an equivalent selected bundle, retaining `sessionId`, `agentId`, parent invocation IDs and sidecar metadata. An Ally service would need to fetch those records under its existing access policy before invoking this importer. No Ally backend API is configured or called by this local plugin. The supplied other-developer export has no adjacent child logs; those gaps remain visible.


## Session directory browser (0.12.0)

From the session directory, run `ally-session browse . --detach`, or use the packaged Python entry point. In Claude Code, use `/ally-session-analyzer:browse <directory>`. Choose `~/.claude/projects` explicitly for the native local library. A chosen root is fixed for that server; launch another directory as a separate library. The server returns its URL and PID. Repeating the command for the same library reopens its running URL. To change launch options, stop that server and relaunch it.

Folder labels show the last two recorded working-directory components; expand for the full folder and log paths. Use search and expandable folders to find a session. **Inspect current log locally** imports the selected parent and adjacent linked children, computes facts and opens the standard source inspector without a model call. **Analyze session** or **Update analysis** uses the configured approved host only after explicit excerpt approval. If the executable is not on PATH, launch with `--claude "/absolute/path/to/claude"`.

One entry per session opens its latest saved analysis, including partial results. Earlier immutable outputs remain internal. `--reports <directory>` admits matching existing `claude-investigation.json` exports at startup without changing the originals. Captured record hashes and child-linkage metadata drive freshness; missing comparison data stays unknown. A completed, current analysis displays Ready even if the developer's task remains unfinished. An update keeps the saved report accessible; a failed update does not replace it. Refresh sessions to rescan. Exports and exact source/proposal copies remain available.

No additional artifact is fetched automatically. For an investigation needing current skill files or historical code snapshots, use the existing `investigate --artifact-manifest ...` workflow, then admit the resulting report directory. Directory browsing needs no Ally access; it is not a team-wide analysis.

### Thinking and unavailable source text

The source inspector identifies thinking-only records without presenting them as assistant statements. It displays captured masked thinking only in a local report exported with source text. Provider-redacted payloads and signatures are never decoded or displayed. Empty content, absent fields, unsupported formats and export omissions have specific notices and no empty code controls.

Expand **Response usage** for exact input/cache/output and separately reported thinking. Those values belong to the reconciled response, which may span multiple source records, and are counted once. Unknown thinking is not zero or the full output count. The investigator's text projection still excludes thinking; empty excerpts are rejected as support for findings.
