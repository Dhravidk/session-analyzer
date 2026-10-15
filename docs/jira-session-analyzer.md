# Build a Claude Code session analyzer with source-linked findings

- **Suggested Jira issue type:** Epic
- **Product:** Ally Session Analyzer
- **Status:** Local prototype implemented; diagnostic evaluation and Ally environment validation remain open.
- **Updated:** October 15, 2026

## Summary

Build a Claude Code plugin and local report viewer that help a developer understand one coding session: what they requested, what the agent actually did, what remains unfinished, and whether a specific improvement is justified.

The analyzer combines deterministic measurements with contextual investigation by approved Claude. Every material conclusion should be inspectable against the original captured evidence. The output is a useful account of the task and its remaining work; a skill or configuration recommendation is optional.

## Problem

Long session logs mix requests, scope changes, tool calls, retries, subagent work and completion claims. A developer may need to inspect many records to establish whether the final revision was checked or why an attempt failed. Aggregate counts and generic advice do not answer those questions.

A repeated call can be legitimate, a failing test can be intentional, and a denied command can reflect correct behavior. The analyzer must investigate the surrounding context before describing these events as problems or recommending a persistent change.

## User story

As a developer, I want to select a Claude session, understand its outcome and unresolved work, and inspect the evidence behind any finding so that I can resume the task or assess an improvement without rereading the entire log.

## Scope and deliverables

| Area | What is being built |
| --- | --- |
| Session navigation | A local library opened from a session directory. Search sessions and folders, show the last two directory components with full paths available, and open one latest saved analysis per logical session. Keep analysis freshness separate from investigation completeness and task success. |
| Evidence foundation | Import supported session logs and available, structurally linked subagent traces. Preserve source identities, original records and revisions. Provide search, surrounding context and paged rereading so an initial preview does not hide relevant evidence from Claude. |
| Task investigation | Have approved Claude identify material requirements, corrections and scope changes; connect each to implementation and verification evidence; and explain completed, contradicted, unverified or superseded work. Preserve competing interpretations and missing evidence. |
| Failure and recovery analysis | Connect the intended result, original attempt, corrections, subsequent checks and remaining gap. Distinguish a genuine recovery from a retry that checked less, or a passing check that predates a relevant edit. Keep unrelated work and overlapping usage out of episode totals. |
| Measurements | Compute calls, tools, input/cache/output usage, recorded durations and observed spans from explicit identities. Expose context/cache changes, recorded compactions and large or truncated tool results with their definitions and coverage. Keep main-agent, child-agent, combined and analyzer usage distinct. |
| Developer report | Present a short task synopsis, outcome, unfinished work, requirements, turns, findings and optional proposals. Provide exact source inputs/results in a collapsible inspector, linked turns, recovery comparisons, copy controls, remaining-work handoff and HTML/JSON exports. Preserve Claude's saved wording. |
| Justified improvements | Support using or narrowly editing an existing skill, creating a reusable skill, or changing CLAUDE.md, hooks, configuration, workflow or prompts when evidence supports that target. Include the exact proposed action, scope, evidence, readiness limits and a falsifiable verification plan. Apply nothing automatically. |
| Distribution | Package the local engine, scripts, MCP tools and Markdown skills/instructions as a standard Claude Code plugin. Keep private logs and generated reports out of the distributable package. |

## How it works

1. The developer selects a session. The local engine preserves the captured evidence, links available children and calculates measurements.
2. With explicit disclosure enabled and a time/cost budget, the managed Claude investigator receives a compact overview and can retrieve more relevant evidence as needed.
3. A separate Claude review process checks the saved draft against sources, requirement outcomes and material contradictions. Revisions, failed checks and incomplete runs remain recorded. Model review is not proof that every conclusion is correct.
4. The viewer renders the saved analysis. The developer can inspect evidence, copy a grounded handoff or proposed edit, and decide what to do next. Opening a finding or source does not trigger a new model call.

The engine uses Python and SQLite for local storage, evidence relationships and measurements. Claude supplies the contextual judgments. Codex is used to build and test the product, not to rewrite production findings or recommendations.

## Acceptance criteria for release

- [ ] One selected root session and its evidenced child relationships define the investigation scope; missing children remain visible and are not counted as zero usage.
- [ ] The opening explains the developer's intent, observed result and material unfinished work. Completion claims agree with the current requirement map and its verification evidence.
- [ ] Material findings link to retained sources. Full saved text, surrounding context and applicable revisions remain accessible; missing, omitted and unsupported content are distinguishable.
- [ ] Recovery tests cover a narrower passing retry, a changed command that resolves the original goal, an expected failure, a correct denial and a passing check followed by a relevant edit.
- [ ] Usage is deduplicated without merging genuine repeated attempts. Cache reads and writes are included within input totals; provider-reported thinking remains within output. Unknown values and captured bytes are not converted into invented token counts or savings.
- [ ] Recorded durations remain distinct from elapsed spans. An input drop alone does not establish compaction, cache eviction or instruction loss.
- [ ] Findings can conclude insufficient evidence or no justified change. An unfinished task alone does not establish plugin fault. Any instruction recommendation considers the actual target/version, existing requirements and overlapping scope.
- [ ] The report preserves saved prose and failed checks. Findings, source inspection, exact copying, exports, subagent details and complete chronology work on desktop and narrow screens with keyboard access.
- [ ] Updating analysis retains the saved report during processing and after a failed update, prevents duplicate jobs, and does not silently present an older analysis as current.
- [ ] The packaged plugin loads and exercises the intended workflow. Mechanical regressions, actual Claude runs and independent diagnostic evaluation are recorded separately.

## Current evidence and remaining work

The local import/accounting engine, managed investigation and review workflow, session library, report viewer and plugin packaging are implemented. Backend, packaging and browser checks have exercised saved reports and explicitly labelled synthetic cases. Real Claude development runs have also been captured with their outputs unedited.

Release confidence still requires:

- Completing interrupted investigation/review checks. Recent recorded runs hit the Claude account limit before final review; their drafts include unresolved errors and must not be presented as validated conclusions.
- Evaluating unseen sessions with independently labelled evidence. Measure unsupported claims, missed material issues, useful actions, uncertainty handling and the developer's time to reach a defensible decision.
- Validating in Ally's approved environment using representative logs, linked child traces and the relevant historical plugin/instruction versions. Local fixtures do not establish Ally compatibility or enterprise compliance.
- Confirming the intended installation and operating-system support. Local CLI loading does not certify every desktop installation path.

No superiority over Claude's `/insights`, production time savings or consistently correct diagnosis has been established.

## Out of scope for this phase

- Cross-session/team-wide analysis, developer rankings and productivity or waste scores.
- Jev integration or an additional unapproved model service.
- Speculative Jira, CI or internal-plugin connectors. Future retrieval must address a material gap in the selected session and use a verified contract.
- Automatic application of recommendations, guaranteed anonymization, or claims of active time, concurrency savings or critical path without supporting telemetry.

## Repository references

- [Governing single-session specification](single-session-investigation-spec.md)
- [Implementation status](implementation-status.md)
- [Validation record](validation.md)
- [Independent evaluation protocol](investigation-evaluation.md)
- [Developer reading-flow release audit](release-audit-0.13.0.md)
