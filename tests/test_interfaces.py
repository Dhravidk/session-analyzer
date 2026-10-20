import io
import json
import os
import select
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from ally_analyzer.engine import analyze_dataset, canonical_report, get_metrics
from ally_analyzer.ingest import import_bundle
from ally_analyzer.mcp import Protocol, serve
from ally_analyzer.service import Service
from ally_analyzer.store import Store
from ally_analyzer.util import canonical
from tests.helpers import response, smoke_rows, write_log

ROOT=Path(__file__).resolve().parent.parent


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.store=Store(self.root/'store'); self.service=Service(self.store); self.protocol=Protocol(self.service)
        self.source=write_log(self.root/'fixture.log',smoke_rows())

    def tearDown(self):
        self.service.close();self.tmp.cleanup()

    def send(self, method, params=None, rid=1):
        r={'jsonrpc':'2.0','method':method,'params':params or {}}
        if rid is not None:r['id']=rid
        return self.protocol.handle(r)

    def init(self,version='2025-06-18'):
        r=self.send('initialize',{'protocolVersion':version,'capabilities':{},'clientInfo':{'name':'test','version':'1'}})
        self.send('notifications/initialized',rid=None)
        return r['result']

    def tool(self,name,arguments=None):
        return self.send('tools/call',{'name':name,'arguments':arguments or {}})['result']

    def wait_job(self,job):
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            status=self.tool('get_job',{'job_id':job['job_id']})['structuredContent']
            if status['state'] in ('completed','failed'):
                self.assertEqual(status['state'],'completed',status)
                return status['result']
            time.sleep(.01)
        self.fail('Background job did not complete')

    def test_handshake_tools_and_input_errors(self):
        self.assertEqual(self.send('tools/list')['error']['code'],-32002)
        self.assertEqual(self.init()['protocolVersion'],'2025-06-18')
        names={x['name'] for x in self.send('tools/list')['result']['tools']}
        self.assertTrue({'import_bundle','analyze_batch','get_metrics','export_report','get_evidence'}<=names)
        self.assertTrue(self.tool('get_metrics',{'analysis_id':'unknown','limit':False})['isError'])
        self.assertTrue(self.tool('get_evidence',{'dataset_id':'x','event_id':'y','allow_content':True})['isError'])
        self.assertEqual(self.send('tools/call',{'name':'nonexistent'})['error']['code'],-32602)
        self.assertEqual(self.send('unknown')['error']['code'],-32601)

    def test_older_protocol_has_text_fallback(self):
        self.init('2024-11-05');r=self.tool('get_definitions')
        self.assertNotIn('structuredContent',r);self.assertIn('definitions',json.loads(r['content'][0]['text']))

    def test_async_import_analysis_export_and_cli_metrics_agree(self):
        self.init()
        imported=self.wait_job(self.tool('import_bundle',{'path':str(self.source)})['structuredContent'])
        analyzed=self.wait_job(self.tool('analyze_batch',{'dataset_id':imported['dataset_id']})['structuredContent'])
        aid=analyzed['analysis_id'];mcp=self.tool('get_metrics',{'analysis_id':aid})['structuredContent']
        cli=subprocess.run([sys.executable,'-m','ally_analyzer','--data-dir',str(self.store.root),'metrics',aid],cwd=ROOT,capture_output=True,text=True,timeout=15)
        self.assertEqual(cli.returncode,0,cli.stderr);self.assertEqual(json.loads(cli.stdout),mcp)
        out=self.root/'report.html'
        exported=self.wait_job(self.tool('export_report',{'analysis_id':aid,'destination':str(out)})['structuredContent'])
        self.assertEqual(exported['path'],str(out.resolve()));self.assertTrue(out.is_file())
        self.assertEqual(self.tool('list_sessions',{'analysis_id':aid,'limit':1})['structuredContent']['total'],1)
        self.assertTrue(self.tool('get_evidence',{'dataset_id':imported['dataset_id'],'event_id':'fake','include_content':True})['isError'])

    def test_annotations_do_not_mutate_canonical_results(self):
        d=import_bundle(self.store,self.source);a=analyze_dataset(self.store,d['dataset_id']);aid=a['analysis_id']
        before=canonical(canonical_report(self.store,aid));fid=next(self.store.items(aid,'finding'))['id']
        cmd=[sys.executable,'-m','ally_analyzer','--data-dir',str(self.store.root),'annotate',aid,fid,'--status','dismissed','--note','Expected fixture behavior']
        r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(before,canonical(canonical_report(self.store,aid)))

    def test_multiple_selection_import_and_collection_default_over_mcp(self):
        self.init()
        second=write_log(self.root/'second.log',[response(100,session='synthetic-second')])
        missing=self.tool('import_bundle',{})
        self.assertTrue(missing['isError'])
        self.assertTrue(self.tool('import_bundle',{'path':str(self.source),'paths':[str(second)]})['isError'])
        imported=self.wait_job(self.tool('import_bundle',{'paths':[str(self.source),str(second)]})['structuredContent'])
        analyzed=self.wait_job(self.tool('analyze_batch',{'dataset_id':imported['dataset_id']})['structuredContent'])
        selected=self.tool('start_session_collection',{'analysis_id':analyzed['analysis_id'],
                            'session_ids':['session-a','synthetic-second'],'purpose':'Synthetic MCP collection'})['structuredContent']
        self.assertEqual(selected['output_mode'],'combined')
        self.assertEqual(len(selected['members']),2)
        self.assertTrue(self.tool('get_metrics',{'analysis_id':analyzed['analysis_id']})['isError'])
        for member in selected['members']:
            scoped=self.tool('get_session_overview',{'investigation_id':member['investigation_id']})
            self.assertFalse(scoped.get('isError'),scoped)

    def test_malformed_stdio_recovers_and_never_logs_to_stdout(self):
        lines=[b'{broken}\n',canonical({'jsonrpc':'2.0','id':1,'method':'ping'}).encode()+b'\n']
        output=io.StringIO();serve(self.store,reader=io.BytesIO(b''.join(lines)),writer=output)
        results=[json.loads(l) for l in output.getvalue().splitlines()]
        self.assertEqual(results[0]['error']['code'],-32700);self.assertEqual(results[1]['result'],{})

    def test_real_stdio_subprocess_and_plugin_entrypoint(self):
        messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'test','version':'1'}}},
                  {'jsonrpc':'2.0','method':'notifications/initialized'},
                  {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                  {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'get_definitions','arguments':{}}}]
        p=subprocess.run([sys.executable,str(ROOT/'bin'/'ally-session'),'--data-dir',str(self.store.root),'mcp'],
                         input=''.join(canonical(m)+'\n' for m in messages),capture_output=True,text=True,timeout=15,cwd=self.root)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stderr,'')
        responses=[json.loads(l) for l in p.stdout.splitlines()]
        self.assertEqual([r['id'] for r in responses],[1,2,3])
        self.assertFalse(responses[2]['result']['structuredContent']['content_disclosure_enabled'])

    def test_page_bounds_and_empty_queries(self):
        self.init();d=import_bundle(self.store,self.source);a=analyze_dataset(self.store,d['dataset_id'])
        aid=a['analysis_id'];first=self.tool('get_tool_calls',{'analysis_id':aid,'limit':2})['structuredContent']
        self.assertEqual(len(first['items']),2);self.assertEqual(first['next_offset'],2)
        second=self.tool('get_tool_calls',{'analysis_id':aid,'limit':2,'offset':first['next_offset']})['structuredContent']
        self.assertFalse({i['id'] for i in first['items']}&{i['id'] for i in second['items']})
        self.assertIsNone(second['next_offset'])

    def test_plugin_manifest_and_relative_launcher(self):
        manifest=json.loads((ROOT/'.claude-plugin/plugin.json').read_text());config=json.loads((ROOT/'.mcp.json').read_text())
        self.assertEqual(manifest['name'],'ally-session-analyzer')
        self.assertEqual(config['mcpServers']['ally-session-analyzer']['args'],['${CLAUDE_PLUGIN_ROOT}/scripts/ally-session.py','mcp'])
        for skill in ('analyze','explain','investigate','review','write-report'):
            self.assertTrue((ROOT/'skills'/skill/'SKILL.md').is_file())


if __name__=='__main__':unittest.main()
