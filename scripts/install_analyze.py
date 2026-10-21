#!/usr/bin/env python3
"""Install only the /analyze shortcut; preserve all unrelated Claude settings."""
import argparse
import os
from pathlib import Path

MARKER = '<!-- session-analyzer-managed-command:v1 -->'
COMMAND = '''---
name: analyze
description: Analyze selected session logs, combine several logs, produce separate answers, or ask a follow-up.
argument-hint: "<log> [<log> ...] [--separate] [question]"
disable-model-invocation: true
---
''' + MARKER + '''

Invoke the installed `ally-session-analyzer:analyze` Skill with these arguments:
$ARGUMENTS

Follow its instructions and use its scoped MCP tools. If that plugin is missing,
report the installation requirement and refer to
https://github.com/Dhravidk/session-analyzer/blob/main/INSTALL.md.
Do not substitute a raw-log read or write an unreviewed analysis.
'''


def install(config_dir, uninstall=False):
    path = Path(config_dir).expanduser().resolve() / 'skills/analyze/SKILL.md'
    if path.is_symlink():
        raise ValueError('Refusing to replace an existing /analyze symlink: ' + str(path))
    if path.exists():
        content = path.read_text()
        if MARKER not in content:
            raise ValueError('An unrelated /analyze already exists; preserve it and resolve the command name conflict: ' + str(path))
        if uninstall:
            path.unlink()
            return str(path)
        if content == COMMAND:
            return str(path)
    elif uninstall:
        return str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # A fixed companion path and exclusive create refuse concurrent replacement.
    pending = path.with_suffix('.installing')
    created = False
    try:
        with pending.open('x') as out:
            created = True
            out.write(COMMAND)
        pending.chmod(0o600)
        # Recheck ownership before replacing a pre-existing managed shortcut.
        if path.exists() and (path.is_symlink() or MARKER not in path.read_text()):
            raise ValueError('The /analyze destination changed; no existing command was replaced')
        os.replace(pending, path)
    finally:
        if created and pending.exists():
            pending.unlink()
    return str(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-dir', type=Path, default=Path(os.environ.get('CLAUDE_CONFIG_DIR', Path.home() / '.claude')))
    parser.add_argument('--uninstall', action='store_true')
    args = parser.parse_args()
    try:
        print(install(args.config_dir, args.uninstall))
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
