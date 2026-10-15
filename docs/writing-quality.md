# Writing quality in the session analyzer

Researched October 13, 2026. These sources informed the writing skill; they do not validate this analyzer or establish that it outperforms `/insights`.

Merriam-Webster describes AI slop as low-quality AI-generated material, often produced in volume. For this product, the relevant problem includes plausible prose with little decision value, rather than a particular punctuation style. [Merriam-Webster](https://www.merriam-webster.com/wordplay/word-of-the-year)

BetterUp Labs and Stanford Social Media Lab describe workplace output that appears useful but shifts interpretation and repair work onto its recipient. Their published survey concerns workers' reported experiences, not a controlled evaluation of this analyzer. We use the practical question: can a teammate act on the recommendation without reconstructing the analysis? [BetterUp research](https://www.betterup.com/workslop)

Nielsen Norman Group's study of product-embedded AI describes difficulty finding answers in lengthy, generic responses. Its writing guidance emphasizes putting the answer first, readable formatting and familiar language. These support a short main readout with evidence available for inspection. [NN/g](https://www.nngroup.com/articles/genai-write-for-the-web/)

## Implemented approach

The packaged `write-report` skill is shared by `analyze`, `explain` and `investigate`. It requires specific evidence, attention to the original request and later recovery, concrete proposed edits, meaningful uncertainty and a follow-up check. It removes generic recommendations, stale fixes, invented benefits and repetitive framing. It allows no recommendation when the evidence does not support one.

Claude loads the skill before drafting and performs its own review before saving. The engine checks source references and structured metrics. The report renderer escapes and displays the saved wording without rewriting it. Codex is used to develop the features and tests, not to edit production recommendations. Neither the skill nor reference validation proves causal explanations or prose accuracy. Quality is assessed against the evidence and the reader's task, not by an AI detector, a banned-word score or a 'slop-free' label.

## Behavioral review

For each real or synthetic example, record the source scope, excerpt selection, host/model, skill versions and inspected evidence. Review these observable outcomes:

- Does each factual claim follow from the cited event, rather than merely cite an existing ID?
- Does the explanation preserve the user's intent, changed scope, later recovery and incomplete traces?
- Is the proposed instruction specific enough to try? Is it already present or already implemented?
- Are unsupported costs, savings, blame and claims about other sessions absent?
- Can the reader identify the finding and next action without reading repetitive setup or unexplained jargon?
- Did shortening the report preserve facts that could change the decision?

Known test traps include a clear prompt followed by agent error, legitimate repeated monitoring, a successful recovery with changed arguments, a scope change, a fix already made, missing child logs, and an instruction embedded in tool output. A polished rewrite that keeps a false claim fails review. A concise report that misses a material issue also fails.

The live synthetic host test verifies writing-skill invocation. Evaluate the exact Claude output, including its mistakes. Record assessments separately; do not silently correct the example, select better sentences from several runs or count outside editing as a product capability. Fix the feature or skill on development cases, then run Claude again. Any Claude critique or revision step used in evaluation must also be part of the shipped workflow.

`scripts/run_claude_investigation.py` in the source checkout runs the packaged workflow on an explicitly selected input. It saves the host transcript, final answer, exact recommendations, HTML report and an origin audit. The audit checks that recommendations match Claude's save calls and that the HTML matches the standard renderer. It does not assess semantic quality. The runner supplies no hand-selected event/topic anchors by default. Use `investigation-evaluation.md` for a broader comparison.
