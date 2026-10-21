#!/usr/bin/env python3
"""Check a plugin's actual MCP entrypoint without Claude, logs or persistent state."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_TOOLS = {'get_definitions', 'get_session_overview', 'prepare_session_reply',
                  'start_session_collection', 'prepare_collection_reply',
                  'get_reviewed_session_reply', 'get_reviewed_collection_reply'}


def check(plugin_dir=ROOT, timeout=20):
    plugin = Path(plugin_dir).expanduser().resolve(strict=True)
    manifest = json.loads((plugin / '.claude-plugin/plugin.json').read_text())
    config = json.loads((plugin / '.mcp.json').read_text())['mcpServers']['ally-session-analyzer']
    expected_args = ['${CLAUDE_PLUGIN_ROOT}/scripts/ally-session.py', 'mcp']
    if manifest['name'] != 'ally-session-analyzer' or config['command'] != 'python3' or config['args'] != expected_args:
        raise ValueError('Unexpected plugin identity or MCP command; inspect the configuration before running it')
    requests = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2025-06-18', 'capabilities': {},
            'clientInfo': {'name': 'session-analyzer-install-check', 'version': '1'}}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
        {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'get_definitions', 'arguments': {}}},
    ]
    with tempfile.TemporaryDirectory(prefix='session analyzer install check ') as folder:
        env = dict(os.environ, ALLY_ANALYZER_HOME=str(Path(folder) / 'store'), ALLY_ANALYZER_ALLOW_CONTENT='0')
        for name in ('PYTHONPATH', 'ALLY_ANALYZER_INVESTIGATION_ID', 'ALLY_ANALYZER_COLLECTION_ID', 'ALLY_ANALYZER_SESSION_ONLY'):
            env.pop(name, None)
        process = subprocess.run([sys.executable, '-I', str(plugin / 'scripts/ally-session.py'), 'mcp'],
            input=''.join(json.dumps(r) + '\n' for r in requests), capture_output=True, text=True,
            cwd=folder, env=env, timeout=timeout)
        if process.returncode != 0:
            raise ValueError('MCP process failed: ' + process.stderr.strip())
        responses = [json.loads(line) for line in process.stdout.splitlines()]
        if [r.get('id') for r in responses] != [1, 2, 3] or any('error' in r for r in responses):
            raise ValueError('Unexpected MCP response IDs or protocol error')
        server = responses[0]['result']['serverInfo']
        if server != {'name': manifest['name'], 'version': manifest['version']}:
            raise ValueError('MCP identity/version differs from the plugin manifest')
        tools = {t['name'] for t in responses[1]['result']['tools']}
        if REQUIRED_TOOLS - tools:
            raise ValueError('Missing MCP tools: ' + ', '.join(sorted(REQUIRED_TOOLS - tools)))
        definitions = responses[2]['result']
        if definitions.get('isError') or definitions['structuredContent']['content_disclosure_enabled'] is not False:
            raise ValueError('Definitions failed or content disclosure was unexpectedly enabled')
    return {'status': 'ok', 'plugin': manifest['name'], 'version': manifest['version'],
            'tools_registered': len(tools), 'content_disclosure_enabled': False,
            'source_imported': False, 'model_invoked': False,
            'limit': 'MCP installation smoke check; not a live Claude review or a semantic-quality certificate.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin-dir', type=Path, default=ROOT)
    parser.add_argument('--timeout', type=float, default=20)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('Timeout must be positive')
    if sys.version_info < (3, 9):
        parser.error('Python 3.9 or newer is required')
    try:
        result = check(args.plugin_dir, args.timeout)
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
