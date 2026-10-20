"""Exercise the shipped archive without the checkout or an installed package."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.package_plugin import build_archive
from tests.helpers import response, write_log


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
                self.assertIn('agents/source-review.md', members)
                self.assertIn('ally_analyzer/session_reply_review.py', members)
                self.assertIn('ally_analyzer/session_collection.py', members)
                self.assertIn('docs/multiple-logs.md', members)
                self.assertIn('ally_analyzer/verified_prices.json', members)
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
                {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'get_definitions','arguments':{}}},
                {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'get_session_guide','arguments':{}}}]
            env=dict(os.environ,ALLY_ANALYZER_HOME=str(root/'isolated store'))
            for name in ('PYTHONPATH','ALLY_ANALYZER_ALLOW_CONTENT','ALLY_ANALYZER_INVESTIGATION_ID','ALLY_ANALYZER_COLLECTION_ID','ALLY_ANALYZER_SESSION_ONLY'):
                env.pop(name,None)
            result=subprocess.run([sys.executable,'-I',*args],cwd=root,env=env,
                input=''.join(json.dumps(m)+'\n' for m in messages),capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stderr,'')
            responses=[json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([r['id'] for r in responses],[1,2,3,4])
            names={t['name'] for t in responses[1]['result']['tools']}
            export=next(t for t in responses[1]['result']['tools'] if t['name']=='export_session_investigation')
            self.assertIn('md',export['inputSchema']['properties']['format']['enum'])
            self.assertTrue({'start_session_investigation','read_investigation_evidence','save_incident',
                'save_requirement_map','export_session_investigation', 'get_session_guide',
                'list_session_investigations', 'query_measurement', 'inspect_response_accounting'} <= names,names)
            self.assertFalse(responses[2]['result']['structuredContent']['content_disclosure_enabled'])
            guide = responses[3]['result']['structuredContent']
            raw = (plugin/'skills/explain/SKILL.md').read_bytes()
            self.assertEqual(guide['instructions'], raw.decode())
            self.assertEqual(guide['sha256'], hashlib.sha256(raw).hexdigest())
            browse=subprocess.run([sys.executable,'-I',str(plugin/'scripts/ally-session.py'),'browse','--help'],
                cwd=root,capture_output=True,text=True,timeout=20)
            self.assertEqual(browse.returncode,0,browse.stderr)
            self.assertIn('--reports',browse.stdout)
            fixture=response(1);fixture['message']['model']='claude-opus-5-5'
            source=write_log(root/'synthetic-model-session.jsonl',[fixture])
            run=subprocess.run([sys.executable,'-I',str(plugin/'scripts/ally-session.py'),'run',str(source)],
                               cwd=root,env=env,capture_output=True,text=True,timeout=20)
            self.assertEqual(run.returncode,0,run.stderr)
            aid=json.loads(run.stdout)['analysis_id']
            summary=subprocess.run([sys.executable,'-I',str(plugin/'scripts/ally-session.py'),'summary',aid],
                                   cwd=root,env=env,capture_output=True,text=True,timeout=20)
            self.assertEqual(summary.returncode,0,summary.stderr)
            data=json.loads(summary.stdout)
            self.assertEqual(data['metrics']['cost_estimate_usd']['value'],'0.000946')
            self.assertEqual(data['configuration']['price_book_source']['kind'],'bundled_verified')
            second=response(10,session='synthetic-second');second['message']['model']='claude-opus-5-5'
            other=write_log(root/'second selected log.jsonl',[second])
            run=subprocess.run([sys.executable,'-I',str(plugin/'scripts/ally-session.py'),'run',str(source),str(other)],
                               cwd=root,env=env,capture_output=True,text=True,timeout=20)
            self.assertEqual(run.returncode,0,run.stderr)
            aid=json.loads(run.stdout)['analysis_id']
            selected=subprocess.run([sys.executable,'-I',str(plugin/'scripts/ally-session.py'),'collection-start',aid,
                     'session-a','synthetic-second','--purpose','Synthetic extracted package'],
                     cwd=root,env=env,capture_output=True,text=True,timeout=20)
            self.assertEqual(selected.returncode,0,selected.stderr)
            selection=json.loads(selected.stdout);cid=selection['collection_id']
            # Exercise the extracted MCP's default gate with synthetic scripted
            # authorship, not a Claude invocation or semantic-review certificate.
            process=subprocess.Popen([sys.executable,'-I',*args],cwd=root,env=env,
                                     stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            def rpc(method,params):
                process.stdin.write(json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params})+'\n');process.stdin.flush()
                return json.loads(process.stdout.readline())
            def tool(name,**arguments):
                result=rpc('tools/call',{'name':name,'arguments':arguments})['result']
                self.assertFalse(result.get('isError'),result)
                return result['structuredContent']
            try:
                rpc('initialize',{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'synthetic-collection','version':'1'}})
                process.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\n');process.stdin.flush()
                group=tool('get_session_collection',collection_id=cid)
                self.assertEqual(group['output_mode'],'combined')
                self.assertEqual(group['collection_readout']['usage']['input_tokens']['cost_usd'],'0.000292')
                entries=[];text=[]
                for member in group['members']:
                    sid=member['session_id']
                    spans={'task_outcome':sid+': Task outcome is unverified from metadata.',
                           'instruction_following':sid+': Instruction following cannot be judged without source prose.'}
                    entries.append({'investigation_id':member['investigation_id'],'compliance':spans});text.extend(spans.values())
                body='Synthetic protocol fixture: obtain evidence before proposing changes.\n\n'+'\n'.join(text)
                draft=tool('prepare_collection_reply',collection_id=cid,sessions=entries,body=body)
                self.assertEqual(draft['status'],'review_required');self.assertNotIn('reply',draft)
                tool('get_collection_reply_draft',collection_id=cid,draft_id=draft['draft_id'])
                ready=tool('submit_collection_reply_review',collection_id=cid,draft_id=draft['draft_id'],sessions=entries,
                           body=body,notes='Synthetic metadata-only submission, not an actual native Agent review.',source_checks=[])
                self.assertEqual(ready['status'],'ready',ready)
                self.assertTrue(ready['reply'].endswith(body))
                self.assertEqual(tool('get_reviewed_collection_reply',collection_id=cid,draft_id=draft['draft_id'])['reply'],ready['reply'])
            finally:
                process.stdin.close();process.wait(timeout=20)
                process.stdout.close();process.stderr.close()


if __name__=='__main__':unittest.main()
