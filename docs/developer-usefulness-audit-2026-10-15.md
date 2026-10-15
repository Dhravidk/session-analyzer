# Developer usefulness audit

October 15, 2026. This is Codex's product audit, not a replacement for any Claude-authored session finding. The underlying reports and all model revisions remain unchanged.

The analyzer is more inspectable than a prose-only retrospective: a developer can trace claims to inputs and results, distinguish narrower verification, inspect missing children, and see an investigation with no recommendation. That architecture is useful. The observed output is not consistently concise or logically consistent enough to call it insightful by default. A writing skill alone will not fix that.

## Evidence reviewed

- The supplied migration report, rendered as `ally-session-0.10.3.html`, still contains the completed 0.8.1 investigation: 32 requests, two findings, six explained recorded failures, no proposals, and 16 unavailable child traces. Its saved title, synopsis, outcome and summary were inspected without revision.
- The fresh `source-explanations-0.10.3-attempt3` run and original fixture: guided synthetic development evidence, not a held-out test.
- The fresh `native-csv-0.10.4` run, actual native Claude Code JSONL, initial/final code and tests, and independent final test execution. This synthetic session was investigated with the default question. Two SDK-submitted requests are present, although the current turn metric excludes their origin.
- The renderer, source inspector and requirement map in the browser. Earlier tests cover long results, child traces, exports and narrow screens; see the release audits for exact boundaries.

## Problems to address first

### 1. A completed label must not hide an unmet material part

In the native CSV report, `fix_roundtrip` combines implementation, reading README/tests, preserving tests, runtime restrictions and reporting in one requirement. The reviewer noticed that the tests were not read before the first change. It revised the explanation but kept `supported_completed`, while the opening still says both requests were completed. The qualification and the headline do not agree at the same scope.

Do not create a checklist for every sentence. Separate material obligations when they can have different outcomes, or explicitly define a requirement's completed scope and excluded obligations. Distinguish product behavior from process compliance. A good result does not prove all requested process steps occurred; a minor process miss does not mean the feature is broken.

Validation: use a fixture where the implementation passes but an explicit material prerequisite is skipped. The opening, requirement statuses and missing-evidence fields must agree. A reviewer must be able to disprove the completion claim, not merely append a caveat.

### 2. The review must propagate corrections to the opening

The fresh reviewer correctly found the missed test-reading instruction and retained a revised map. The saved title still says “both done.” In the red/green fixture, “explain what changed” was accepted even though the final response gives only a thin completion statement; the reviewer itself calls the explanation thin. A text artifact being present is not sufficient evidence that it answers the requested question.

Add semantic review examples for partial answers and mixed outcomes. Require a changed material conclusion to trigger review of the title, synopsis and outcome against the current map. This belongs in Claude's investigation/review contract; the renderer must not rewrite or relabel prose to hide the discrepancy.

Validation: the current output should fail a consistency review when its opening overstates a qualified requirement. Keep the rejected draft and let Claude author a new revision.

### 3. Explicitly account for SDK task requests

The native CSV source has two user-role requests with `turnOrigin: sdk`. The existing metric intentionally excludes explicit non-human origins. Consequently the UI shows zero turns, no turn drill-down, and nine responses outside a turn. Claude incorrectly describes this as absent turn records rather than an exclusion by policy. It can read the requests as events, but the mandatory main-request reading gate has an empty population.

Introduce an explicitly named task-request population, preserving human, SDK, inferred and control-message provenance. Keep the human/user metric's definition honest. Do not make SDK requests human by relabelling them. Use the eligible task population for investigation coverage and expose why a request is excluded. This is a local import/policy change, not an Ally connector.

Validation: interactive requests, external SDK requests, tool results, notifications, compaction summaries and automatic continuation messages must remain distinct. An SDK task must not pass request coverage merely because the denominator is zero. Test parent links and attribution before introducing SDK turn views.

### 4. Use available evidence before repeating an avoidable limitation

The native investigation repeatedly says final files were not read. Four snapshots were admitted, including the final implementation and tests, but neither host inspected those final snapshots. Their current-snapshot status properly limits historical claims; it does not make them useless for checking the final state. The task's Write/Edit inputs also provide direct recorded evidence.

A material gap should lead to one of three clear outcomes: inspect the available relevant evidence, explain why it cannot answer the question, or record an actual budget/access stop. Repeating “not read” is not a substitute for investigation. Conversely, do not require a redundant readback when recorded edit inputs, success and relevant tests already support a bounded claim.

Validation: give the investigator an admitted final snapshot that answers a declared material question. Check whether it inspects it or justifies not using it. Do not require irrelevant artifacts to be fetched.

## Writing that reads like AI slop

The main problem is repetitive or mechanically cautious analysis, not flowery adjectives.

| Observed pattern | Why it is unhelpful | Better contract for future Claude output |
| --- | --- | --- |
| Title, synopsis, outcome and summary repeat the same fail/edit/pass chronology in the red/green report. The migration opening likewise repeats the test counts and killed rerun. | More reading without another decision or explanation. | Give each field a distinct job: task context; current result and unfinished work; detailed reasoning behind evidence controls. Omit a redundant summary. |
| The native requirement heading is an entire semicolon-separated request containing many obligations. | It is hard to scan, and one status conceals mixed results. | A short authored requirement label plus scoped details and separate material obligations. Keep the full original request in its source. |
| “Read each cited source; the chronology matches.” | A review-process assertion does not explain what the evidence proves. | State the decisive relation, such as why the six-test result occurs after the final test edit. |
| “Passing tests establish those tests' result, not correctness beyond them.” | Often a generic caveat; it does not identify an uncovered behavior. | Name a relevant uncovered case or revision when known. Keep the general accounting rule in definitions. |
| Repeated warnings that a compaction's effect was not established in the red/green example. | No supported compaction-causality claim was being made; the warning distracts from the task. | Include a caveat beside a decision it changes. Recorded compaction metadata can remain in Metrics. |
| “Final file contents were not read directly” in several places in the native report. | Repetition adds no evidence and can conceal available investigative work. | Inspect relevant admitted evidence, or state the specific unresolved claim once. |

The new sentence “Reports PASSED at r1 on the same fixture; a summary, not raw output” is useful: it explains the exact record's relevance and its limit. Other sentences, such as “Error text” or “Denial message,” merely rename the record. Nonempty citation text is not a useful explanation by itself. The source sentence should identify the attempted action, decisive result, or particular support/contradiction for the linked claim. Preserve explicit uncertainty when the record cannot settle it.

## Make the developer's next decision easier

1. **Separate immediate work from persistent improvements.** The migration report ends with an unverified rerun and no proposed change. Zero persistent recommendations is defensible. Still, the developer needs a clear view of the unresolved test result and what evidence would close it. A source-linked next check is not automatically a skill or CLAUDE.md proposal.
2. **Prioritize unresolved work over recovered mechanics.** The native report gives a denied Bash action and ambiguous Edit substantial attention even though both recovered. Keep these details accessible; do not make every recovered error an opening headline. Derive prominence from saved task impact and uncertainty, not failure counts.
3. **Name evidence before the click.** “Finding 1” and “Source 3” require opening controls to learn their purpose. Use a short Claude-authored label when saved, with the full why-sentence in the inspector. Do not invent a renderer summary or borrow another finding's explanation.
4. **Give long sessions a task map.** A few source-linked milestones and latest requirement states would help a reader navigate 32 turns without another summary of every message. This is a proposed feature, not something the current report automatically supplies.
5. **Keep investigation status separate from task status.** “Investigation completed” can coexist with unfinished implementation. The opening should make both states clear. A completed review is not a completion certificate for the coding task.
6. **Measure whether the analysis earns its cost.** The two fresh investigations took about 190 and 215 seconds and reported about $1.11 and $1.33 of analyzer cost. These small examples justify testing a bounded first pass with deeper review for material unresolved claims; they do not prove a particular cost-saving strategy. Compare missed issues and developer decision time, not word count alone.
7. **Put a material review qualification beside the affected status.** The native finding displays “expected · recovered · supported,” while its saved review says the denial's expectedness is unproven. The qualification is available under the saved-review disclosure, but the prominent status is easy to overread. Preserve both saved judgments and show the conflict beside the label; do not silently replace either one. Test that a reader can identify the disagreement without opening unrelated details.

## What should stay

Keep exact source access, paged rereading, explicit missing children, all token categories, unknown states, separate elapsed spans, immutable reviews and optional recommendations. The native analyzer correctly rejected the interim three-test pass as verification of the new BOM tests. The migration report distinguishes a background completion notice from failing test output. Those are concrete useful distinctions.

Do not add a general instruction for every ignored requirement. Do not call successful recovery waste. Do not add a skill merely to fill the report. Do not infer plugin fault from unfinished work or use workload statistics as quality thresholds. A small evidence graph helps navigation and identity accounting; it does not solve these semantic or writing problems.

## Next evaluation

Keep the [independent evaluation protocol](investigation-evaluation.md): label unseen sessions before analyzing them, use the same evidence for comparisons, blind reviewers, and measure unsupported claims, omitted material requirements, correct qualifications, useful actions and time to answer developer questions. Include sessions with no justified recommendation. Add the mixed-completion, thin-answer and SDK-origin cases above to development regressions, but do not score the tuned fixtures as independent evidence.

The current tool supports better scrutiny. Whether it produces more useful decisions than `/insights`, or saves developers time overall, remains unmeasured. Calling it “slop-free” would exceed the evidence.
