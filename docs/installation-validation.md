# Installation validation — 2026-10-20

The GitHub installation instructions were exercised against the private
`Dhravidk/session-analyzer` repository at commit
`1ccfa6e041908d8698fddf00810537baf97aa369`. Plugin identity and version remain
`ally-session-analyzer` **0.22.2**. This is an installation checkpoint, not a
clearance of the [live review failures](release-live-audit-0.22.2.md).

## Environment and results

Tested on macOS with Python 3.9.6 and Claude Code 2.1.299.

| Check | Result |
| --- | --- |
| Full offline unittest suite | 423 tests run: 421 passed, two optional private-fixture skips. |
| Separate packaging/process suite | All seven checks passed, including clean-extraction MCP checks and bounded subprocess behavior. |
| Clean local checkout marketplace installation | Add, install, list, details and uninstall passed in a temporary Claude configuration. |
| GitHub HTTPS marketplace installation | Clone, add, install, list, details and uninstall passed in a separate temporary Claude configuration using existing Git authentication. |
| Installed component inventory | Six skills, one `source-review` agent and one `ally-session-analyzer` MCP server. |
| Actual installed MCP entrypoint | Initialize, list tools and metadata-only definitions passed; 62 tools registered and source-text disclosure disabled. |
| New installation smoke-check regressions | Four tests passed, covering environment isolation, command validation, missing replies and a timed-out synthetic process. |
| Repository hygiene | Reviewed staged paths and diffs; historical tracked paths and credential-pattern scan had no hits. Private evidence, authentication data and archives stayed ignored. |

`claude plugin validate` passed with the expected warning that a plugin-root
`CLAUDE.md` is not loaded as runtime project context. The root file is a guide
for agents reading or working in this repository; packaged skills and the
reviewer agent supply runtime instructions. See [installation](../INSTALL.md).

Both installation trials used fresh `CLAUDE_CONFIG_DIR` directories and removed
them afterward. They did not change the user's existing Claude plugin settings.
The smoke check opened a temporary store and imported no session logs. No model
analysis, `claude -p` request or paid reviewer was invoked for this checkpoint.

The pre-existing frozen 0.22.2 release ZIP was neither rebuilt nor uploaded.
Its SHA-256 remained
`87e5ad27f722e868abf7b48e7eae08dd579233f4686809d56d5fd4c349f6c9d4`.
Repository history was retained, rather than replaced by an installation snapshot.

## What this does not establish

Installation proves that this host can discover the components and run the local
MCP protocol. It does not validate future task/compliance judgments, paid reviewer
invocation counts, interrupted native-agent resume, or other host/platform
versions. The existing live release blockers remain open. No stable release or
public distribution was performed.
