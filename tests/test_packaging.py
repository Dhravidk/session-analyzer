"""Exercise the shipped archive without the checkout or an installed package."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.package_plugin import build_archive


class PackagingTests(unittest.TestCase):
    def test_archive_runs_from_path_with_spaces_outside_checkout(self):
        with tempfile.TemporaryDirectory(prefix='ally plugin package ') as folder:
            root=Path(folder)
            first=build_archive(root/'one.zip');second=build_archive(root/'two.zip')
            self.assertEqual(first['sha256'],second['sha256'])
            plugin=root/'unpacked plugin';plugin.mkdir()
            with zipfile.ZipFile(first['path']) as archive:
                members=set(archive.namelist())
                self.assertIn('scripts/ally-session.py',members)
                self.assertEqual(len([n for n in members if n.endswith('/SKILL.md')]),6)
                self.assertTrue({'ally_analyzer/session_library.html','ally_analyzer/session_library.js',
                                 'ally_analyzer/session_library.css'} <= members)
                self.assertFalse(any(n.startswith(('.analysis/','tests/','variants/','output/')) for n in members))
                self.assertTrue(all(not n.endswith(('.sqlite','.jsonl','.log','.pyc')) for n in members))
                self.assertTrue(archive.getinfo('bin/ally-session').external_attr >> 16 & 0o111)
                archive.extractall(plugin)
            config=json.loads((plugin/'.mcp.json').read_text())['mcpServers']['ally-session-analyzer']
            args=[value.replace('${CLAUDE_PLUGIN_ROOT}',str(plugin)) for value in config['args']]
            messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{
                'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'package-regression','version':'1'}}},
                {'jsonrpc':'2.0','method':'notifications/initialized'},
                {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'get_definitions','arguments':{}}}]
            env=dict(os.environ,ALLY_ANALYZER_HOME=str(root/'isolated store'))
            for name in ('PYTHONPATH','ALLY_ANALYZER_ALLOW_CONTENT','ALLY_ANALYZER_INVESTIGATION_ID','ALLY_ANALYZER_SESSION_ONLY'):
                env.pop(name,None)
            result=subprocess.run([sys.executable,'-I',*args],cwd=root,env=env,
                input=''.join(json.dumps(m)+'\n' for m in messages),capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stderr,'')
            responses=[json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([r['id'] for r in responses],[1,2,3])
            names={t['name'] for t in responses[1]['result']['tools']}
            self.assertTrue({'start_session_investigation','read_investigation_evidence','save_incident',
                'save_requirement_map','export_session_investigation'} <= names,names)
            self.assertFalse(responses[2]['result']['structuredContent']['content_disclosure_enabled'])
            browse=subprocess.run([sys.executable,'-I',str(plugin/'scripts/ally-session.py'),'browse','--help'],
                cwd=root,capture_output=True,text=True,timeout=20)
            self.assertEqual(browse.returncode,0,browse.stderr)
            self.assertIn('--reports',browse.stdout)


if __name__=='__main__':unittest.main()
