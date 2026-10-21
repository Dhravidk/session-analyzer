# Install Session Analyzer in Claude Code

The repository is `Dhravidk/session-analyzer`. The plugin keeps its existing name,
`ally-session-analyzer`, so its commands start with `/ally-session-analyzer:`.

**Status:** 0.22.2 is a development candidate. Installation and offline checks
work independently of the [known live review failures](docs/release-live-audit-0.22.2.md).
Use it for evaluation; it is not a certified compliance verdict or a cleared
production release.

## Requirements

- Python **3.9 or newer**, available as `python3` on the PATH used by Claude Code.
- Claude Code with plugin and native Agent support. The current live checks used
  **2.1.299** on macOS; other versions and platforms need their own verification.
- Git and access to the GitHub repository. A private repository requires existing
  GitHub authentication for Git, even if you are signed in to the website.
- An approved, authenticated Claude account for later model-written analysis.
  Import, accounting and the smoke check do not require a model call.

The Python engine uses the standard library. Installing a Python package with
`pip`, an API client, Node.js or a database server is not required.

## Install from GitHub

Run in a terminal:

```sh
claude plugin marketplace add https://github.com/Dhravidk/session-analyzer.git
claude plugin install ally-session-analyzer@session-analyzer --scope user
claude plugin list
claude plugin details ally-session-analyzer
```

`user` scope makes the plugin available across your projects on this computer.
For just your current project, use `--scope local` on installation and run from
that project. `--scope project` writes shared project configuration; choose it
only when the project should declare the plugin for collaborators.

Restart Claude Code, or run `/reload-plugins` in an existing session. The details
should show the six skills (`analyze`, `browse`, `explain`, `investigate`,
`review`, `write-report`), the `source-review` agent and the
`ally-session-analyzer` MCP server. A successful install proves configuration,
not the accuracy of a future analysis.

The root `CLAUDE.md` guides agents working with this repository. Claude Code may
warn that it is not loaded as plugin context; that is expected. Runtime guidance
comes from the packaged skills and reviewer agent instead.

## Load a checkout for one session

This alternative leaves persistent plugin configuration unchanged:

```sh
git clone https://github.com/Dhravidk/session-analyzer.git
cd session-analyzer
python3 scripts/check_install.py
claude --plugin-dir .
```

From another project, pass the absolute checkout path to `--plugin-dir`. Do not
point it at `variants/jev/`: that is retired development history. A source
checkout is sufficient; no release ZIP needs to be downloaded or built.

## Check the local server without sending logs to a model

From a checkout:

```sh
python3 scripts/check_install.py
```

This starts the actual stdio MCP entrypoint in an isolated temporary store,
lists its tools and requests metadata-only definitions. It imports no source,
does not invoke Claude, and does not change your existing store or settings.
It exits nonzero on a failed handshake, missing tools, an unexpected disclosure
state or a timeout. `--plugin-dir /absolute/path/plugin` checks another installed
or extracted plugin directory instead.

## First use and source-text disclosure

Installation starts with metadata-only disclosure. For task/compliance judgments,
controlled source excerpts must be authorized by the operator. If you want to
allow that for a session, launch Claude Code yourself with:

```sh
ALLY_ANALYZER_ALLOW_CONTENT=1 claude
```

An installing agent must not enable it on your behalf without that authorization.
Pattern masking is incomplete; choose the log and approved account accordingly.
Then use [one-log or multi-log commands](docs/user-guide.md). No logs are imported
just because you installed the plugin.

The default store is `~/.ally-session-analyzer`. To keep a dedicated store, set
`ALLY_ANALYZER_HOME=/absolute/path/private-store` before launching Claude Code and
reuse that path for follow-ups. Do not commit the store or private logs.

## Troubleshooting and updates

| Symptom | Check |
| --- | --- |
| Repository not found | Confirm repository access and Git authentication. Website sign-in alone may not authenticate Git. |
| `python3` not found | Make Python 3.9+ available to the terminal/desktop process that launches Claude Code; restart that process. |
| Plugin installed, commands absent | Check `claude plugin list`, reload plugins or restart, and use the full `/ally-session-analyzer:explain` name. |
| MCP failed to connect | Run `scripts/check_install.py` on the plugin directory. Preserve the error; do not bypass the server with direct private-file reads. |
| Content-dependent analysis unavailable | The operator must authorize controlled excerpts; metadata-only setup is not a failure. |
| Existing investigation opens unexpectedly | Check `ALLY_ANALYZER_INVESTIGATION_ID` and `ALLY_ANALYZER_COLLECTION_ID`; do not carry another run's scope binding into a new selection. |

To update an installed marketplace version:

```sh
claude plugin marketplace update session-analyzer
claude plugin update ally-session-analyzer@session-analyzer
```

Reload afterward. To remove the plugin, use
`claude plugin uninstall ally-session-analyzer@session-analyzer`. Removing the
plugin does not itself authorize deleting saved analysis stores.

These commands follow the official [marketplace installation flow](https://code.claude.com/docs/en/plugin-marketplaces)
and the installed CLI's `--help`. For agent-driven setup, see
[the installation checklist](docs/agent-install.md). The
[installation checkpoint](docs/installation-validation.md) records the clean
local and GitHub installation trials and their limits.
