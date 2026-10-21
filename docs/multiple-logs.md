# One log or several

The existing conversational skill accepts either option:

```text
/analyze /absolute/path/session.jsonl
/analyze /absolute/path/one.jsonl /absolute/path/two.jsonl
/analyze /absolute/path/one.jsonl /absolute/path/two.jsonl --separate
```

Natural requests such as “analyze these four logs together” work too. Multiple roots default to a combined developer handoff. `--separate` is interpreted by the skill as `output_mode=individual`; it is not a Claude CLI flag. One root retains the existing single-session review flow. Copies of one root do not become separate sessions.

The combined message keeps the established style: source cost and token-dollar breakdown, recommendations, why/session evidence, a concise compliance section, supported exact skill/tool edits, and an optional copy-paste Claude prompt last. Each log gets its own task-outcome and instruction-following assessment; the usual evidence summary is about three sentences per log. Default answers omit cache/compaction diagnosis and tuning; their accounting, events, tools and requested follow-ups remain available. Historical Nithin messages and Claude answers are not rewritten. Findings and edits still need source/target support; there is no required recommendation or generated compliance score.

## Tool flow

1. `import_bundle(path=...)` for one file/directory/ZIP, or `import_bundle(paths=[...])` for one to twenty explicitly selected JSONL/.log files. Supply exactly one argument. Adjacent child collection remains enabled by default. Poll `get_job`, then call `analyze_batch` and poll again. No pricing-network/model call is involved.
2. Use `list_sessions` to resolve exactly the selected roots. A wider archive is not permission to analyze every root. Before opening any one investigation, call `start_session_collection(analysis_id, session_ids, purpose, output_mode)`. An identical selection resumes the same collection and member scopes. `get_session_collection` reopens it and returns each member's investigation ID, request inventory and cost, plus the deduplicated aggregate.
3. Every source reader/query still names one member investigation. Assess each root separately, including original requests, queued updates, applicable instructions, ending, later recovery and counterevidence. The connection cannot access unselected sessions or legacy global readers. A bound single-session connection cannot widen into a collection. A new selection requires an unbound connection or an operator-selected binding; the agent cannot bypass this limit.
4. `prepare_collection_reply` saves a complete authored draft with one assessment entry per member. Combined mode supplies one `body` containing all exact compliance spans and no per-member bodies. Individual mode omits the combined body and supplies each member's body and spans. With content enabled, unread indexed requests/updates block drafting. The backend adds only numeric cost facts, never findings or recommendations.
5. A valid draft returns `review_required`. The host automatically invokes the packaged native `ally-session-analyzer:source-review` Agent with collection/draft IDs. That fresh reviewer rereads every member after draft creation, then checks the synthesis and submits `submit_collection_reply_review`. This single pass reviews the roots separately and the combined advice; it does not repeat a whole reply-review cycle per log. Every source check names its investigation ID, fresh read request and literal quote. It covers both compliance aspects for every root. Retrieve `get_reviewed_collection_reply` and copy only its accepted reply, verbatim. No extra user review prompt or initial-draft fallback.

Replays retain the same draft/review progress; at most two distinct review submissions are permitted. A saved review validates exposure, source linkage and format, not entailment, caller identity or universal correctness. Missing/failed review stays incomplete. Native Agent provenance and writing quality require a live host check; offline scripted submissions are synthetic protocol tests, not Claude-authored examples.

For a saved collection, keep its store and set `ALLY_ANALYZER_COLLECTION_ID` when reconnecting. Do not also set `ALLY_ANALYZER_INVESTIGATION_ID`. Metadata-only selection works without enabling source disclosure; compliance judgments requiring prose remain unverified. The model must not enable disclosure itself.

## Costs and output size

The combined first line shows only the estimated total for the union of captured source response frames under the pinned verified rate card. Token/component amounts, pricing notes and shared-response reconciliation details are available on request through the same scoped tools. It reconciles copied/overlapping responses once, including shared history and streaming updates. It does not add inclusive per-root totals, cumulative host snapshots, parent-reported child rollups or analyzer/reviewer usage. Unknown rates, conflicts, interrupted usage and missing child traces retain their limits. Per-root figures remain available for attribution; they can overlap and must not be added. The API estimate is not a subscription charge or invoice.

A combined default body has a maximum of `450 + 150 × (roots − 1)` words, allowing concise evidence per log without forcing an entire batch into a single-session limit. Each individual body retains its 450-word maximum. The tool rejects overlong drafts for the author to revise; it never shortens saved prose. Explicitly requested resource topics retain the existing detail exception.

## Offline CLI

```sh
python3 scripts/ally-session.py run /path/one.jsonl /path/two.jsonl
python3 scripts/ally-session.py collection-start ANALYSIS_ID SESSION_ONE SESSION_TWO --purpose 'Review selected tasks' --mode combined
```

`run` performs import/accounting, not model investigation. The collection tools are also available through `session-call OPERATION ARGUMENTS.json`. The managed `investigate` command and the browser library's analysis button retain their existing one-root saved-report workflow; the conversational `explain`/`analyze` skills provide the new multi-log handoff. No global hooks or host-model settings change.

## Validation

Run `python3 -m unittest tests.test_session_collection tests.test_interfaces tests.test_packaging -q` for synthetic scope, accounting, disclosure, immutable review, CLI, MCP and extracted-package checks. The ordinary full suite remains offline. The private real-log accounting exercise is `python3 scripts/test_offline_collection.py --source /path/one.jsonl --source /path/two.jsonl`; it blocks network/subprocess calls and preserves selected source bytes. It produces computed facts, not a newly reviewed narrative. Live Claude testing remains deferred until the operator confirms limits have reset.
