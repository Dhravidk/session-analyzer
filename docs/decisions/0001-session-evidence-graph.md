# Session evidence graph decision

October 14, 2026 · Accepted for 0.4.0; model-level performance evaluation pending

Use a small evidence graph implemented as indexed SQLite relationships alongside the current source and accounting tables. Its purpose is to retrieve relevant context and preserve provenance within one session. It does not establish causes, require a separate graph database, or imply a measured speed improvement.

The governing behavior is in the [single session investigation specification](../single-session-investigation-spec.md).

## Why relationships help

A timestamp window can miss the result of a long-running call, a delegated agent's output, the request that motivated an action, or a repair much later in the session. Explicit links let the investigator follow those connections while keeping unrelated concurrent activity separate. Text search is still needed for relationships that were not recorded.

The current implementation already has graph ingredients: event IDs and parent UUIDs, response-to-call attribution, call/result identity, and some delegation metadata. Materializing them makes their basis, scope and retrieval behavior explicit. This is an extension of existing storage rather than a reason to replace the Python engine with another runtime.

## TraceForge precedent

The inspected TraceForge revision is `e617f7f6c19909d28f3b18ff719ed49ac4beebb1`, also the remote HEAD observed on October 14, 2026. Its [schema](https://github.com/Dhravidk/TraceForge/blob/e617f7f6c19909d28f3b18ff719ed49ac4beebb1/traceforge/schema.jac) defines runs, steps, file artifacts, patches, test events and hypotheses, with typed links such as `NextStep`, `TouchesFile`, `RunsTest` and `EvidencedBy`. Reuse that distinction between entities and relationships, and the idea of returning locatable evidence to the investigator.

Do not port its benchmark failure taxonomy or cross-run clustering into this single-session product. Its current [feature rules](https://github.com/Dhravidk/TraceForge/blob/e617f7f6c19909d28f3b18ff719ed49ac4beebb1/traceforge/features.jac#L208-L217) infer recovery from passing substrings and count return-code phrases without checking the numeric code. Its [loop rule](https://github.com/Dhravidk/TraceForge/blob/e617f7f6c19909d28f3b18ff719ed49ac4beebb1/traceforge/features.jac#L288-L296) can be triggered by three search-command hits. These illustrate why graph structure must not confer factual authority on heuristic labels.

TraceForge's [structured pack](https://github.com/Dhravidk/TraceForge/blob/e617f7f6c19909d28f3b18ff719ed49ac4beebb1/traceforge/eval.jac#L687-L734) selects candidate windows and applies a final character cap. Ally must retain pagination and source rereading instead of making that selection the investigator's only evidence. Its [deterministic comparison](https://github.com/Dhravidk/TraceForge/blob/e617f7f6c19909d28f3b18ff719ed49ac4beebb1/traceforge/eval.jac#L940-L965) adds a score to the structured arm when a cluster exists. Ally's evaluation must judge evidence and decisions without rewarding the chosen representation by construction.

The transferable idea is navigable, attributed evidence. Diagnostic accuracy and lower context use still need independent tests.

## Graph contract

Node types reference existing entities where possible: session, agent run, source event, model response, tool invocation, artifact snapshot, incident, claim, proposal and check. Do not create a node for every word or embed all raw content into graph payloads.

Every relationship has endpoints, type, scope, source references, extraction or author version, and basis: `recorded`, `derived`, or `interpreted`. Derived means a reproducible transformation of identified evidence; it does not mean a causal relationship. Interpreted edges are stored separately from the deterministic projection and identify their author and review status.

| Relationship | Permitted basis and limit |
| --- | --- |
| Session contains run or event | Recorded identity and admitted scope membership. |
| Parent event to child event | Explicit parent UUID resolved within scope; unresolved/conflicting links remain diagnostics. |
| Response emits call | Recorded tool-use identity in that response. |
| Call has result | Matching recorded call/result identity; retain conflicts and missing results. |
| Call delegates to run | Structured delegation evidence; a missing trace is explicitly unavailable. |
| Next in recorded order | Derived navigation order within the recorded agent scope; never causal or proof of serial execution. |
| Event references path | Recorded reference to a path; does not prove the file was read or changed. |
| Event reads or writes snapshot | Requires captured content or equivalent version evidence and a supported outcome, not just a path mention. Partial content remains partial. |
| Check evaluates snapshot | Requires a known artifact version and check binding; a nearby timestamp is insufficient. |
| Instruction applies to event | Interpreted unless a supported harness record explicitly establishes application. |
| Event belongs to incident | Usually interpreted; retain membership rationale and evidence. |
| Evidence supports or contradicts claim | Attributed interpretation, except for narrow mechanically checked claims. |
| Attempt recovers incident | Interpreted unless an explicit supported task contract establishes recovery. |

Temporal adjacency, common paths and similar error text are retrieval hints. They are not evidence that an action caused a failure or that a later success fixed the same issue. Do not introduce a deterministic `caused_by` edge from these signals.

## Storage and traversal

Use a relationship table with scope, endpoint identifiers and types, relation type, basis, source-reference payload, and extractor version. Index both traversal directions using scope, endpoint and relation type. Keep source records and normalized accounting as the authoritative inputs.

Key the projection by source set, scope, adapter and relationship versions. Rebuilding an index must not mutate source IDs or silently replace interpretations from a previous run. Text caches also include projection and disclosure-policy versions. Indexes and cached text remain private local data and must participate in deletion and retention handling.

Use bounded adjacency queries or recursive queries with visited-node tracking and explicit limits. SQLite supports [recursive queries over trees and graphs](https://www.sqlite.org/lang_with.html#queries_against_a_graph) and [indexes for constrained lookups](https://www.sqlite.org/queryplanner.html). Whether either improves this workload depends on the queries and build cost.

Return edge provenance and continuation details with each neighbourhood. Prefer explicit call/result, parent and delegation links before expanding display-order links. Expose ambiguous alternatives rather than selecting a plausible parent without evidence. Do not assume the entire graph is acyclic or that a missing path proves absence.

Keep text retrieval independent. [SQLite FTS5](https://www.sqlite.org/fts5.html) is an optional implementation candidate, not a requirement for the first graph slice. Detect runtime availability. Preserve literal search for arbitrary command strings; full-text tokenization is not the same search contract. A cached literal scan is a valid fallback.

## What could become faster

| Work | Plausible improvement | Remaining limitation |
| --- | --- | --- |
| Find a call's result or child run | Indexed identity links avoid rediscovering relationships | These joins already partly exist; measure the incremental gain |
| Retrieve ancestors and related checks | Bounded relationship traversal can replace repeated broad inspection | Missing or ambiguous links still require search and interpretation |
| Search visible text repeatedly | Cached projection avoids repeated JSON parsing and masking | This is a caching benefit, not evidence of a graph benefit |
| Assemble evidence for Claude | Return relevant linked records together and deduplicate repeated excerpts | Smaller input is useful only if material evidence is retained |
| Complete the investigation | Fewer retrieval round trips may reduce latency and usage | Model reasoning, more careful review and missing artifacts can dominate |

Building a projection costs time and storage. On a short session analysed once, a direct indexed query or scan may be sufficient. No percentage speedup or token saving is promised.

## Required comparison

Compare three paths on the same single-session cases:

1. **Current baseline:** the current context-window, literal search and reread workflow.
2. **Indexed flat baseline:** cached visible text and direct indexed call/result/metadata queries, without general multi-hop traversal.
3. **Graph-assisted retrieval:** the same cache and indexes plus typed relationship traversal.

Use both mechanical retrieval queries with known relevant records and actual Claude investigations. Hold available sources, disclosure, model and budget policy fixed. Where tools differ, record that difference. Do not cripple the flat baseline with prefix-only truncation or deny it source rereading.

Measure build time, cold and warm query latency, storage, memory, returned evidence completeness, model/tool round trips, investigator token usage when reported, end-to-end latency, diagnostic errors and reviewer effort. Count actual usage rather than converting characters into a claimed token measurement. Include interleaved agents, missing children, distant recovery, long results, punctuation-heavy searches and successful sessions.

Adopt additional traversal complexity only if it improves evidence retrieval or review/investigation efficiency without a material loss of correctness relative to the indexed flat baseline. Set numerical budgets and materiality criteria before evaluating the held-out cases. If caching supplies the benefit and multi-hop traversal does not, retain the simpler retrieval path. A graph database, embeddings, graph-wide summarization and a visual graph explorer remain deferred.

## Initial implementation measurement

The 0.4.0 local benchmark uses one public synthetic session with 1,001 events and known target records. After reusing SQLite connections, median warm literal search was 22.36 ms for the legacy scan, 16.09 ms for the cached flat path and 15.86 ms for the same cached search in the graph path. All three found the prescribed records. The shared scope/graph build took 89.94 ms and text cache population 40.41 ms in that run.

For one-hop call/result retrieval, direct indexed lookup took 0.53 ms and the general graph operation 5.40 ms. This does not establish a graph speed benefit. Both original slower-cache measurements and optimized results are retained locally. The script `scripts/benchmark_session_retrieval.py` records the budgets, coverage and limitations. There were no model calls; cold OS caches, independent end-to-end arm timings, semantic quality and reviewer effort were not measured. The required model comparison above remains pending.
