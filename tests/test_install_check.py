"""Synthetic/local installation checks; no Claude or network invocation."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.check_install import ROOT, check


class InstallCheckTests(unittest.TestCase):
    def synthetic_plugin(self, folder, code):
        plugin = Path(folder) / 'synthetic plugin'
        (plugin / '.claude-plugin').mkdir(parents=True)
        (plugin / 'scripts').mkdir()
        for name in ('.claude-plugin/plugin.json', '.mcp.json'):
            (plugin / name).write_bytes((ROOT / name).read_bytes())
        (plugin / 'scripts/ally-session.py').write_text(code)
        return plugin

    def test_actual_mcp_ignores_inherited_disclosure_scope_and_store(self):
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder) / 'existing store'; original.mkdir()
            (original / 'sentinel.txt').write_text('Synthetic existing state')
            env = {'ALLY_ANALYZER_HOME': str(original), 'ALLY_ANALYZER_ALLOW_CONTENT': '1',
                   'ALLY_ANALYZER_INVESTIGATION_ID': 'synthetic-unavailable',
                   'ALLY_ANALYZER_COLLECTION_ID': 'synthetic-unavailable', 'ALLY_ANALYZER_SESSION_ONLY': '1'}
            with patch.dict(os.environ, env):
                result = check()
            self.assertEqual(result['status'], 'ok')
            self.assertFalse(result['content_disclosure_enabled'])
            self.assertFalse(result['model_invoked'])
            self.assertEqual(list(original.iterdir()), [original / 'sentinel.txt'])
            self.assertEqual((original / 'sentinel.txt').read_text(), 'Synthetic existing state')

    def test_unexpected_command_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin = self.synthetic_plugin(folder, "raise RuntimeError('Must not execute')")
            path = plugin / '.mcp.json'; config = json.loads(path.read_text())
            config['mcpServers']['ally-session-analyzer']['command'] = 'unexpected-command'
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, 'Unexpected plugin identity or MCP command'):
                check(plugin)

    def test_missing_protocol_responses_do_not_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin = self.synthetic_plugin(folder, "print('{}')")
            with self.assertRaisesRegex(ValueError, 'Unexpected MCP response'):
                check(plugin)

    def test_unresponsive_mcp_is_bounded_and_reaped(self):
        with tempfile.TemporaryDirectory() as folder:
            plugin = self.synthetic_plugin(folder, 'import os,time\nfrom pathlib import Path\n'
                "Path(__file__).with_suffix('.pid').write_text(str(os.getpid()))\ntime.sleep(30)\n")
            with self.assertRaises(subprocess.TimeoutExpired):
                check(plugin, timeout=.5)
            pid = int((plugin / 'scripts/ally-session.pid').read_text())
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)


if __name__ == '__main__':
    unittest.main()
