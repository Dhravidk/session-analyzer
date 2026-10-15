# Working on the session analyzer

Double-check claims and preserve uncertainty. Claude-authored investigation output must remain unedited; renderer changes must not manufacture findings or recommendations.

## Local version history

- Use this repository for the tool's source, tests, skills and documentation.
- Commit completed work in small, coherent commits with a concrete description. Keep unrelated changes separate and run the checks appropriate to each change.
- Review staged paths and diffs before committing. Keep raw developer sessions, analysis stores, credentials, generated reports, screenshots and release archives out of Git. Clearly labelled synthetic fixtures belong under `tests/fixtures/`.
- Preserve existing history and user changes. Do not backdate commits or present a snapshot import as the actual sequence of earlier development.
- Keep repository operations local. Do not add a remote or push without the user's instruction.

See [development workflow](docs/development.md) for checks and the initial baseline's scope.
