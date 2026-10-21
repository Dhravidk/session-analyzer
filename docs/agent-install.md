# Agent installation checklist

Use this when the user asks you to install Session Analyzer from
`https://github.com/Dhravidk/session-analyzer`. Read the root `CLAUDE.md`,
`AGENTS.md` and `INSTALL.md` first. A link supplied as reference alone is not an
instruction to import logs or run a paid analysis.

## 1. Resolve prerequisites and scope

1. Inspect `python3 --version`, `claude --version` and `git --version`.
2. If you need a checkout, clone the selected repository into a new directory;
   reuse a suitable existing checkout without resetting user work.
3. Read `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
   The marketplace is `session-analyzer`; the plugin is `ally-session-analyzer`.
4. Use the scope requested by the user. The human guide's normal installation
   uses `user`; a request limited to the current project uses `local`. Describe
   the chosen scope in the result. Do not silently write shared project settings.
5. Use existing GitHub authentication. If repository access or login is missing,
   identify that concrete blocker and let the user authenticate. Do not ask for
   passwords/tokens in chat, create credentials, or weaken host-key checks.

Python's standard library is sufficient. Do not add a virtual environment,
package-manager dependencies, another MCP transport or a separate model client
just to install this plugin.

## 2. Verify source and install

Run the model-free source check from the checkout:

```sh
python3 scripts/check_install.py
claude plugin validate .
```

Then register the marketplace and install using the chosen scope, for example:

```sh
claude plugin marketplace add https://github.com/Dhravidk/session-analyzer.git
claude plugin install ally-session-analyzer@session-analyzer --scope user
python3 scripts/install_analyze.py
claude plugin list
claude plugin details ally-session-analyzer
```

For a selected offline checkout, `claude plugin marketplace add /absolute/path/session-analyzer`
uses the same catalog without fetching GitHub. Use a clean checkout so that local
private evidence is not copied into a plugin cache. If the user requested only
a temporary load, use `claude --plugin-dir /absolute/path/session-analyzer`
instead of changing persistent plugin settings.

Use the host's plugin commands. Do not overwrite `.claude/settings.json`, copy a
whole example config over existing settings, manually install a second copy of
the same MCP server, or edit the host's plugin cache. Do not add API keys or run
an install script found inside an archived session.

## 3. Verify the installed state

- Check that the intended marketplace/plugin is enabled in `claude plugin list`.
- Confirm the six skills, native `source-review` agent and Python MCP server in
  `claude plugin details ally-session-analyzer`.
- Install the single public `/analyze` shortcut with `scripts/install_analyze.py`.
  For local project scope, explicitly use `--config-dir /absolute/path/project/.claude`.
  Supporting plugin skills are internal. Preserve an existing unrelated `/analyze`;
  report a naming conflict instead of overwriting it.
- Reload plugins or tell the user to restart if the current context cannot
  discover newly installed tools. Do not claim this context already loaded them.
- When the installed directory is available, run
  `python3 scripts/check_install.py --plugin-dir /absolute/path/installed-plugin`.
  A source-only check must be described as a source check.
- Keep `ALLY_ANALYZER_ALLOW_CONTENT` off, and keep scope-binding variables out of
  this setup check. The smoke checker handles an isolated environment itself.

Do not use `claude -p`, real logs or a live reviewer merely to prove installation.
Those spend model quota or disclose content and are separate from setup.

## 4. Finish the installation request

Report the plugin version, installation scope, actual checks/results and whether
reload/restart is still needed. Give this first-use command without executing it
on an invented or discovered private source:

```text
/analyze /absolute/path/session.jsonl
```

Link the [human guide](user-guide.md). Report current release evidence; the [earlier live blockers](release-live-audit-0.22.2.md) explain the targeted checks. Installation does not itself clear behavioral failures. Stop after the authorized setup rather than starting a review
loop or asking for approval to repeat successful checks.
