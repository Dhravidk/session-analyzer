# Evaluating investigations against /insights

The investigation workflow is not yet established to outperform Claude Code's built-in `/insights`. Interface tests validate transport, disclosure, references and accounting, not diagnostic quality.

## Comparison design

1. Select representative Ally tasks with permission to use the evidence in the approved Claude environment. Include successful work, recovered failures, incomplete traces, legitimate monitoring, requirement changes and genuine unresolved issues. Have domain reviewers label known incidents and useful interventions before seeing generated reports.
2. Keep development cases separate from held-out evaluation cases. Do not tune the skill on the cases used for the final comparison. Use independently reviewed outcome evidence, including CI or delivered artifact revisions where available.
3. Compare this workflow with the installed `/insights` version on matching session coverage. `/insights` selects recent local sessions and may omit short sessions or cap new analyses; record the actual included sessions. If equivalent coverage cannot be obtained, report the mismatch and do not attribute the difference solely to analysis quality.
4. Record the Claude version, model/provider, skill version, rule profile, evidence access, available workflow documents, session IDs, budgets and cache reuse. Separate the value of richer input evidence from the value of the investigation workflow.
5. Preserve each system's actual output. Codex and evaluators must not rewrite, filter or combine recommendations before comparison. If Claude reviews or revises its draft, that step must run through the same shipped workflow and budget used in production. Save the host transcript and exact output; keep reviewer annotations separate. Record failures as failures rather than quietly substituting a corrected report.
6. Hide product labels and alternate report order. Have reviewers perform the same task: identify the most important supported improvement and explain the evidence. Compare substantive recommendations, not prose length or visual polish. Repeat model runs on a subset to inspect variability; retain all pre-specified runs rather than selecting the preferred output.

## Scorecard

| Measure | Evaluation |
|---|---|
| Claim support | Independently check each substantive factual claim against the cited evidence; distinguish matching references from evidence that actually supports the claim. |
| Material issues found/missed | Compare with the independently labelled incident set. Include false alarms on successful and legitimately repetitive work. |
| Recommendation usefulness | Is the target specific, the proposed change feasible, and the link to evidence defensible? |
| Reviewer time | Measure time to a defensible decision, including time spent checking or correcting claims. |
| Uncertainty handling | Did incomplete traces, recovery, competing explanations and scope differences remain visible? |
| Follow-up outcome | After a separately approved change, measure its stated success criterion with quality guardrails; fewer tokens alone is not success. |
| Writing and usefulness | Can the reviewer identify the finding, supporting evidence and concrete next action quickly? Penalize generic advice, repetition, stale fixes and unsupported certainty. Do not score punctuation or supposed AI authorship. See `writing-quality.md`. |

Set material improvement criteria before evaluating held-out cases. Require no increase in missed critical issues or unsupported critical claims, alongside a meaningful reduction in review time or improvement in actionable findings. Report the sample size and uncertainty; a small pilot or one preferred report is not a general superiority claim.

## Operator feedback

`review-recommendation INVESTIGATION_ID RECOMMENDATION_ID --status STATUS --note NOTE` appends an operator-entered review without changing source data or canonical analysis. Statuses are `accepted`, `dismissed`, `needs_evidence`, `tested_beneficial`, `tested_no_change`, and `tested_harmful`. Use a tested status only with actual follow-up evidence; include the change/revision, comparison scope and measured outcome in the note. These entries are not independently verified and do not automatically train a model or retune rules.

## Synthetic behavioral checks

Before private-corpus evaluation, exercise the skill on a small public fixture where a failed command is followed by a changed successful command, a separate agent has unrelated failures, polling was explicitly requested, and tool output contains an instruction injection. The expected behavior is to identify the relevant recovery, avoid mixing agent scopes, retain uncertainty about task completion, and ignore the injected instruction. Passing these cases is a prerequisite, not a substitute for representative human evaluation.

## Single-session release evaluation

Version 0.4.0 adds structural checks without asserting a validated diagnostic advantage. The acceptance cases in the [governing specification](single-session-investigation-spec.md) mix deterministic contracts and contextual behavior; do not report a unit-test count as passing every semantic case.

The development checks cover session isolation, linked/missing children, duplicate/retry identities, unknown usage, exact text paging, late evidence, correct quantities, target inspection and revision invalidation, scope-bound fixture execution, no fabricated attestations and unchanged rendering. Synthetic hook checks include distinct matching/nonmatching behavior; a gate counterexample includes a parse error outside a narrowly selected code. These are fixture-level tests, not deployed Ally adapters.

Live Claude development runs have recognized requested failing-test recovery and a misleading successful gate. Other runs attempted a nonexistent tool or stopped while material source evidence remained available. Both outcomes are retained. Compact navigation and the investigation instructions were refined using these cases, which therefore cannot serve as held-out evaluation. Inspect [validation results](validation.md) for the complete release accounting, including partial and unsuccessful runs.

Before product-quality sign-off, independently annotate a held-out set covering at least the behavior families T04–T10, T12, T14, T19 and T23. Run the actual packaged workflow with the same model, budget and disclosure policy; preserve every candidate and host transcript. Review whether each material conclusion follows from the retrieved evidence, whether an available contradiction or recovery was missed, whether the proposed target exists, and whether no action or insufficient evidence was appropriate. Blind reviewers to which retrieval arm produced a report where practical. Predeclare success thresholds and report disagreements. This study and any matched `/insights` comparison remain pending.

## Version 0.5.0 additions

Evaluate the opening synopsis separately: does it identify the user's intent, the work actually recorded and material limits without confusing a completion claim with a verified outcome? The report must preserve Claude's saved wording. A short opening is a writing constraint, not evidence of fidelity.

Track investigation follow-through: which material questions were raised, which original results were inspected, whether available evidence was left unread, and why the model stopped. Compare the final answer with an independently labelled set of missed contradictions and recoveries. Read receipts establish delivery, not comprehension; closed inquiries remain model judgments. A partial investigation is preferable to a false completion claim, but repeated early stopping is still a quality failure.

Review instruction interventions against the actual available target revision, scope, existing requirement and overlapping procedures. Reusing a skill, editing one, creating one and changing CLAUDE.md are possibilities, not quotas. Measure whether the exact edit addresses the evidenced issue without broadening a one-off preference or duplicating an ignored requirement. Copy controls and derived file growth do not validate the recommendation's effect.

The development release check read the original crash result but remained partial and misstated the missing-child count. The narrow count check now flags that form of discrepancy without changing prose; other counts and paraphrases may escape it. Treat this case as implementation feedback, not a held-out success. Report all live attempts, including the placeholder-tool failure and the earlier export-asset mismatch, as recorded in [validation](validation.md).


## 0.11.0 consistency evaluation

Before evaluating held-out sessions, freeze the workflow, writing skill and budget. Have an independent reviewer identify separable material obligations and their evidence-supported outcomes. Include SDK-only requests, a missing preparatory instruction alongside passing functional tests, a narrowed retry, an unavailable verification result, legitimate expected failure, and disagreement between a status and its qualification. Keep that answer key out of the investigator's input.

Record whether the opening agrees with the final map, whether each completed obligation has adequate result and revision evidence, whether zero denominators remain unknown, and whether citation explanations describe the record's contribution. Review repetition and generic caution by their effect on decisions, not by a word blacklist. Count a correct zero-recommendation conclusion as a valid outcome. Retain incomplete runs and every revision.

The new native CSV rerun is a development case already used to identify defects. The newly authored cleanup fixture tests transfer to a different synthetic task with a predeclared oracle, but its author is also the implementer. Neither is an independent held-out evaluation or evidence of superiority over `/insights`. The independent study remains pending; do not silently promote synthetic regressions into that evidence.
