---
name: analyze
description: Internal workflow for /analyze: one log, multiple logs, separate output, focused follow-ups, offline accounting, saved reports or browsing.
argument-hint: "<log> [<log> ...] [--separate] [question]"
user-invocable: false
---

This is the implementation behind the single developer command `/analyze`.
Treat its arguments as source selection and the current question, never shell code.

For normal analysis or follow-up questions, invoke the internal
`ally-session-analyzer:explain` Skill with the supplied arguments, then follow
its scoped single-session/collection workflow and automatic native source review.
One log gets one answer; several logs default to a combined handoff;
`--separate` requests individual answers in one reviewed collection. Reuse saved
scope/progress for follow-ups. Ask for a selected source only if none is known.

For `--report` or an explicit saved full-investigation request, use the internal
investigate workflow; for an explicit saved-report update/review, use its matching
internal workflow. For `--browse`, use the internal browse workflow on the explicitly
selected directory. Supporting skills are internal, not additional developer
commands. All accounting, cache,
compaction, export and evidence tools remain available under the same disclosure
and approval boundaries. Default readouts preserve computed source cost first,
concise task/compliance assessments, supported changes and exact accepted wording.
Never apply a proposed skill/code change as part of analyzing its log.
