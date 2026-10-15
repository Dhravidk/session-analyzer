# Initial Git baseline validation

October 15, 2026. The existing 0.12.1 source tree was imported into local `main` in 18 commits grouped by subsystem, followed by this validation record. The history starts from the current implementation; it does not recreate earlier edits. The annotated `v0.12.1` tag marks the complete baseline, including this record.

A fresh local clone of `371c8c5badb64823e70f96971216533282230738` ran `python3 -m unittest discover -s tests -v`: 236 tests discovered, 234 passed, two optional private-corpus tests skipped, in 21.805 seconds. The clone contained neither `.analysis/`, generated `output/`, nor release `dist/`. Packaging regression tests built and exercised an extracted plugin outside that clone. No live Claude investigation or external service call was required. The later validation commit changes documentation only.

`git fsck --no-dangling` and staged whitespace checks passed. The repository has no remote. The three labelled synthetic JSONL fixtures are tracked; raw session files, corpus inventories, credentials, analysis stores and generated deliverables are ignored. The retired Jev prototype is labelled as historical source and remains excluded from the baseline plugin package.

Local receipts are retained in `.analysis/git-baseline/`: `commit-plan.json`, `commits.json`, `clone.log`, `clean-checkout-tests.log` and `clean-checkout-validation.json`. These receipts and prior analysis output remain outside Git. This validation establishes that the tracked baseline is locally restorable and passes its existing mechanical tests; it adds no new claim about diagnostic quality, Ally compatibility or live-model behavior.
