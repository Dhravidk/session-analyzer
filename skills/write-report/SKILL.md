---
name: write-report
description: Write or edit Ally Session Analyzer explanations and recommendations in clear, specific prose grounded in the selected session evidence. Use before saving insights or presenting an analysis.
metadata:
  version: write-report-v11
---

Write for a teammate deciding whether anything should change. Make the evidence, optional action and important limit easy to find. Apply these rules inside Claude's investigation to saved claims, proposals and the final answer. The renderer preserves your exact saved words; Codex is not a production editor. This skill does not authorize applying a change or accessing more data.

## Earn each recommendation

- State what the record shows before interpreting it. Cite evidence IDs in saved observations and counterevidence. In prose, use readable source labels or file/line references when available. A valid reference does not prove the sentence it accompanies.
- An assistant's statement in a transcript establishes what it said, not that its diagnosis or count was correct. Do not reuse an unverified statement as a measured baseline. Verify it against suitable evidence or leave the baseline to be measured.
- Check the user's request, subsequent corrections and later recovery. Do not turn an explicitly requested activity into waste. A tool error can be incidental. A later scope change is not proof the original prompt was deficient.
- Check whether the proposed fix already happened. Follow available later evidence before saving; an arbitrary context-window boundary is not a reason to stop when it could change the advice. If a fix happened, identify it and suggest retaining or testing it in future work only when useful. Do not give stale repair advice. A passed command establishes that check's result, not completion of the whole task.
- Name the concrete target and proposed change. For a prompt, supply the actual replacement or addition and its triggering situation. For a skill, prefer a small edit to an existing relevant skill; identify the procedure and the proposed instruction. Do not invent a path, claim a skill was loaded without evidence, or treat a current file as its historical version.
- Separate an observed problem from a possible cause. State a material alternative or missing fact. Avoid invented alternatives added to fill a field; say the cause is unresolved when that is the supported conclusion.
- Use registered measurements for material numerical claims, with their scope and coverage. Do not infer cost from bytes, waste from token volume, execution time from timestamp gaps, or team-wide prevalence from one session. This investigation concerns one root session and admitted children. Turn-pattern shares describe reconstructed turns, not quality or time spent. Prompt tokens include cached reads and writes; do not add them twice.
- Keep this session's preferences scoped to this session. A chosen document size, file count or workflow step is not a universal requirement. Do not report your own tool-call counts or context savings unless an execution record or measurement supplies them.
- Include an observable follow-up check. Describe proposed benefits as something to test. Do not promise a percentage improvement or call a change proven because its description sounds plausible.
- Return fewer recommendations, or none, when evidence is weak. Do not fill space with advice to be clearer, test more, improve collaboration or optimize workflows. A recommendation that fits almost any session needs more evidence or should be removed.
- Distinguish a useful finding from an actionable remaining change. Use no-action or insufficient-evidence conclusions when warranted. Name the missing evidence and the judgment it prevents. A failure, denial or repeated call can be expected behavior.
- State readiness accurately: an uninspected target needs evidence; a planned test has not run; zero checked metrics means zero checked metrics. A passed fixture establishes its tested conditions, not universal correctness or realized benefit. Include a disconfirming outcome in the verification plan.

## Write plainly

Give each opening field a separate job: the title identifies the task, the synopsis explains intent and observed work, and the outcome states the supported result and unfinished gap. Detailed chronology belongs in the finding. A long compound title, repeated test totals and repeated generic caveats do not become more useful by appearing in several fields.

For a pattern, distinguish its shared characteristic from each same-goal episode. Put the exact unresolved question in that episode's `open_questions`; leave recovered episodes as supporting detail. Evidence links and linked turns are not occurrences. State evidence relationships explicitly rather than expecting a renderer to shorten or interpret a paragraph. A recovery reference and an unknown overall outcome may coexist; explain that distinction without implying that all members were fixed.

For each reader-facing source reference, save `explanation`: one short sentence stating what that specific record shows and why it matters to the linked claim. Name the action or result and preserve any limitation that changes its meaning. Read the cited range first; use exact ranges when the full record is not needed. A tool invocation shows an attempt, not successful execution; a participant's statement shows what was said, not independent verification. Do not repeat a whole finding, use generic “this supports the analysis” wording, or add a recommendation. A source can have different explanations in different claim contexts. The report displays the sentence verbatim beside the evidence, and keeps the complete saved source and exact copying available.

Lead with the useful finding or decision. Use ordinary words, active verbs and specific nouns. Keep paragraphs short enough to scan, with one point each. Keep technical names when they identify the actual file, tool, error or behavior; explain unfamiliar terms once.

Remove introductory praise, sales language, rhetorical questions, grand conclusions and repeated summaries. Avoid phrases such as "delve into", "leverage synergies", "unlock potential", "seamless", "robust solution" and "it's worth noting" when a concrete statement will do. Avoid invented labels and forced "not X, but Y" constructions. Punctuation and a word blacklist are not reliable tests of quality.

Keep the main readout short: the finding, relevant evidence, proposed change and key limit. Use a table only for a real comparison, and headings only when they help navigation. Keep IDs, detailed counts and provenance in supporting detail. Do not repeat the same claim under observation, hypothesis, impact and conclusion. Preserve qualifications that change the decision even when shortening the text.

## Review the draft before saving or presenting

Check each substantive sentence against the evidence already inspected. For a causal claim, compare the decisive input expression and observed result literally, then identify the runtime or configuration facts the mechanism requires. Quoting a shell assignment and quoting a later expansion are different operations; JSON escaping is not shell syntax. Do not infer a shell or its options from a tool name. If runtime evidence is missing, describe the observed effect and qualify the mechanism. Do not substitute a familiar failure explanation for the actual input. Remove unsupported statements; label unresolved explanations. Check names, numbers, chronology, recovery and proposed edits. Remove duplicate advice. Make the recommendation executable without making the reader invent its missing steps. If more evidence is necessary, request it through the analyzer's existing disclosure controls.

Illustrative wording, not a finding about the selected session:

Weak: "Enhance validation to streamline the development workflow."

Useful: "The edit was rejected because the file changed after the earlier read. The next read and edit succeeded. Keep that recovery in the editing procedure: after this error, reread the file and rebuild the patch from its current contents. Check whether the same rejection recurs. This example does not establish who changed the file."

A style pass is not a factual verifier or a guarantee that a report is free of low-quality AI output. Do not award a 'slop-free' badge, an AI-authorship score or an unmeasured quality rating. Report what was actually checked.

## Session opening

Give the opening fields different jobs. `synopsis.text` is one to three sentences identifying the developer's intent and what work was done. `observed_outcome.text` states what is supported as complete, what remains unfinished, and any decision-changing evidence gap. `summary` explains the reasoning behind the conclusion; it is supporting detail, not another chronological recap. Do not paste the same chronology or caution into all three. Keep the title short enough to identify the task, without listing every failure and qualification. Read the requests, current requirement map and relevant results before writing. Do not convert a completion claim into a verified result. Supply source references and keep each missing-evidence statement beside the affected claim, once. The renderer has no summarization step and will not improve your wording.

An explanation such as “Error text” or “Denial message” tells the reader what kind of source it is, not why it matters. Write what the record establishes about this claim: for example, “The editor rejected this replacement because the anchor occurs twice, so this attempt made no change.” Use that sentence only when the selected record actually establishes it. Do not infer a result from a call.

Use a short requirement description that identifies the obligation; put its scope and reasoning in their dedicated fields. Keep an ambiguous instruction's competing readings visible, rather than writing a confident procedural failure and qualifying it later. Where a current gap supports an immediate next check, save the requirement's optional `next_action` with the specific action, verification, sources and limits. Do not invent a next check to fill the opening. The copyable handoff is assembled from saved fields, not generated or polished by the renderer.

For proposed instruction changes, give the exact target, scope and literal edit or invocation only after inspecting the relevant snapshots and overlapping instructions. An existing requirement that was ignored calls for diagnosis, not another copy of the same rule. Reuse instructions where appropriate; do not turn a one-off request into a persistent instruction. Show remaining evidence and validation limits without repeating the recommendation across turns.

## Failure explanations

Write each saved failure explanation for someone unfamiliar with this session. Give the purpose of the attempted action, the specific observed failure, and its follow-up. Usually one or two sentences for `summary` and one for `follow_up` are enough. Use filenames or short command fragments only when they explain the failure; leave full commands, timestamps and raw output in the evidence view. Do not merely translate an enum into words or restate an exit code.

Say what the output establishes and what it leaves unknown. A command can produce useful output and still exit unsuccessfully. A missing search match, expected negative test or correctly rejected action is not automatically a defect. A subsequent success must address the same failed action before calling it recovered. Compare the original goal, input set and scope with the later result; a shorter retry or a successful empty search may leave part of the goal unresolved. An incidental read error is not automatically an expected test. No-action does not mean no issue occurred. Keep an unresolved cause or unverified recovery explicit without repeating generic caveats. These explanations explain the recorded attempts; they do not need a recommendation, praise or a general lesson.

## Completion and attribution

Keep the opening focused on requested work, observed outcome, material blockers, justified next action and uncertainty. Use the requirement map to separate completed, contradicted, unverified, superseded and withdrawn work. Do not claim the inventory is complete solely because every request was read. Do not repeat each requirement in the opening.

Separate material obligations when their outcomes differ. Functional completion does not erase a missed instruction to read tests first, preserve an interface, or verify a particular scope. Keep a shared requirement only when the obligations share the same supported outcome; do not expand every sentence into a checklist. A completed label cannot coexist with a status basis acknowledging that a material part was missed. Compare the opening with the final map after any revision. Likewise, an “expected” or “recovered” label must agree with its qualifications; an uncertainty note cannot silently retract the label.

Name a verification gap precisely: a reduced case set, a pass before a later edit, a missing artifact revision or an unsupported completion assertion. Report recovery resources as associated usage, not waste. The developer may need to finish a task even when plugin fault is not established. Do not prescribe a permanent instruction for that immediate next step without evidence of a persistent defect or reusable benefit.
