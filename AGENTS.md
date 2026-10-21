# Working on the session analyzer

Double-check claims and preserve uncertainty. Claude-authored investigation output must remain unedited; renderer changes must not manufacture findings or recommendations.

## Local version history

- Use this repository for the tool's source, tests, skills and documentation.
- Commit completed work in small, coherent commits with a concrete description. Keep unrelated changes separate and run the checks appropriate to each change.
- Review staged paths and diffs before committing. Keep raw developer sessions, analysis stores, credentials, generated reports, screenshots and release archives out of Git. Clearly labelled synthetic fixtures belong under `tests/fixtures/`.
- Preserve existing history and user changes. Do not backdate commits or present a snapshot import as the actual sequence of earlier development.
- Keep repository operations local. Do not add a remote or push without the user's instruction.

See [development workflow](docs/development.md) for checks and the initial baseline's scope.

## Installation and onboarding

- For an installation request, follow [INSTALL.md](INSTALL.md) and the
  [agent installation checklist](docs/agent-install.md). Claude Code working in
  a checkout also reads the root [CLAUDE.md](CLAUDE.md); URL-based installers
  should read it explicitly. It is not loaded as plugin runtime context.
- Run `python3 scripts/check_install.py` for a model-free, metadata-only MCP
  smoke check. Installing the plugin is not permission to read private logs,
  enable source disclosure or launch paid analyses.
- Human usage is in [the user guide](docs/user-guide.md); the current system map
  and Mermaid diagram are in [architecture](docs/architecture.md).
- Preserve the release status in [the live audit](docs/release-live-audit-0.22.2.md).
  Repository publication or successful setup does not clear a failed live gate.
