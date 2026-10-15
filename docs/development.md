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
