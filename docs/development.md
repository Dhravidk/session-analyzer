# Local development and history

The repository records the session analyzer's source, tests, skills and documentation. Its first source-controlled baseline is the existing 0.12.1 implementation, imported on October 15, 2026 in commits grouped by subsystem. These import commits are reviewable slices of one snapshot, not a reconstruction of the earlier development sequence. Use the final `v0.12.1` tag as the complete initial checkout; intermediate import commits can depend on files added by later import commits.

The [baseline validation record](git-baseline-validation.md) documents the clean-checkout test and tracked-data boundaries.

Subsequent work should use small, independently usable commits: make one coherent change, run the relevant checks, review the staged diff, and commit with a description of the behavior changed. Keep unrelated work separate. Do not amend prior history unless explicitly requested.

```sh
git status --short
git diff
git add -- path/to/changed/file
git diff --cached --stat
git diff --cached
git commit -m "Describe the specific change"
git log --oneline --decorate
```

The full local regression suite uses the standard library:

```sh
python3 -m unittest discover -s tests -v
```

Private-corpus tests require explicit `ALLY_TEST_SESSION` and `ALLY_TEST_ARCHIVE` paths; without them they skip. They are separate from the distributable synthetic fixtures. Live Claude investigations remain explicit operations through the approved workflow and its disclosure controls, not part of routine Git commits or the default regression suite.

Build the distributable plugin with `python3 scripts/package_plugin.py`. Packaging tests exercise a clean extraction outside the checkout. The source tree includes the retired Jev experiment under `variants/jev/` solely as development history; it is not part of the approved baseline or its distributable package.

Raw sessions, `.analysis/`, generated `output/`, release `dist/`, private corpus inventories, credentials and caches stay local and ignored. Existing validation documents refer to some of these local artifacts; cloning the source repository does not copy those artifacts. Synthetic fixtures under `tests/fixtures/` are intentionally tracked.

No Git remote is configured. Commits and tags provide local history, not an off-device backup. Adding a remote or publishing the repository requires a separate user instruction.


For an opt-in headless Claude exercise on locally generated, clearly synthetic evidence:

```sh
python3 scripts/test_claude_conversation.py --claude /absolute/path/approved/claude
```

This runs three questions in one real Claude conversation, first with metadata-only disclosure and then with controlled synthetic excerpts. It saves the immutable tested plugin, prompts, raw transcripts, unedited answers and checks under `.analysis/claude-conversation/`. The $3 default cap and 600-second timeout cover the exercise; resumed host usage is reserved conservatively. Mechanical checks verify guide delivery, registered queries, source-accounting inspection, retained child collection, policy enforcement and preservation of saved judgments. Read the answers and sources separately to evaluate correctness. A passed tool-use test is not a semantic-quality pass. Rejected attempts remain in the audit.


For an opt-in two-turn check of the developer readout in the approved Claude host:

```sh
python3 scripts/test_claude_readout.py --claude /absolute/path/approved/claude
```

This uses a labelled synthetic session and a $2 total allowance. It checks the computed first sentence, a default reply that keeps resource detail on request, the requested follow-up, original accounting and executed-tool policy. Prompts, immutable tested package, every answer, rejected attempts and raw host traces remain under `.analysis/claude-readout/`. The formatting check does not certify factual correctness or reliable behavior across models. No private developer log is used.

For an explicitly selected real log, with permission to send controlled excerpts to the approved Claude host:

```sh
python3 scripts/test_claude_developer_reply.py --source /absolute/path/session.jsonl --allow-content --claude /absolute/path/approved/claude
```

This exercises the default conversational reply and its automatically invoked native source-review Agent in ONE user turn, with a $3 cap and 600-second timeout. No second review prompt is sent. `--effort high` selects a higher-effort test without changing user host settings. It preserves the immutable tested ZIP, question, raw transcript, unedited answer and audit under `.analysis/claude-developer-reply/`. Checks cover the exact computed opening, visible authored assessments, fresh request/update exposure, verbatim accepted reply, one native Agent launch, accepted submission from that child, decisive source reads linked to that child, default topic scope, tool policy and unchanged source/accounting. Host trace linkage is checked rather than accepting a review assertion from the parent. Review the actual claims against their sources separately. It is a source-reviewed conversational answer, not a completed full managed investigation or a guarantee of accuracy. Host quota errors and interrupted runs remain failed checks; do not retry through another account or count them as passed. The development harness and selected logs are excluded from the distributable ZIP.
