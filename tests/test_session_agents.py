"""Synthetic parent/child collection and report behavior, with explicit missing logs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ally_analyzer.engine import analyze_dataset
from ally_analyzer.ingest import import_bundle
from ally_analyzer.service import Service
from ally_analyzer.session_agents import get_subagent_details
from ally_analyzer.session_report import report_data, render_report
from ally_analyzer.session_scope import exposure, get_scope, read_investigation_evidence, start_session_investigation
from ally_analyzer.store import Store
from ally_analyzer.util import AnalyzerError
from tests.helpers import call, response, result, write_log
from tests.test_session_workflow import human

ROOT=Path(__file__).resolve().parent.parent


def linked_fixture(folder, renamed=False):
    folder=Path(folder); child=folder/'session-a/subagents'
    parent=write_log(folder/('session.log' if renamed else 'session-a.jsonl'),[
        human(0,'Synthetic fixture: inspect a component using a research subagent.'),
        call(1,'Agent',{'description':'Inspect component','prompt':'Read the component and report the result.'}),
        result(2,'tool-1','Child launched.',meta={'agentId':'child-a','status':'async_launched','totalTokens':999999,'totalToolUseCount':999}),
        call(40,'Agent',{'description':'Check missing child','prompt':'An intentionally unavailable child trace.'}),
        result(41,'tool-40','Child launched.',meta={'agentId':'missing','status':'async_launched'}),
        response(90,content=[{'type':'text','text':'Synthetic parent ending; child execution remains separately inspectable.'}])])
    rows=[call(3,'Read',{'file_path':'/synthetic/component.py'}),result(4,'tool-3','CHILD_ONLY_SENTINEL: component source.'),
          call(5,'Agent',{'description':'Inspect nested test','prompt':'Read the test.'}),result(6,'tool-5','Nested child launched.',meta={'agentId':'child-b','status':'async_launched'}),
          call(7,'Bash',{'command':'python3 missing.py'}),result(8,'tool-7','Exit code 2\nSynthetic file not found.',True),
          response(9,content=[{'type':'text','text':'CHILD_FINAL_SENTINEL: found a missing fixture.'}])]
    write_log(child/'agent-child-a.jsonl',rows)
    (child/'agent-child-a.meta.json').write_text(json.dumps({'toolUseId':'tool-1','agentType':'researcher'}))
    write_log(child/'agent-child-b.jsonl',[call(10,'Read',{'file_path':'/synthetic/test.py'}),result(11,'tool-10','NESTED_ONLY_SENTINEL: test source.'),response(12)])
    write_log(child/'agent-unlinked.jsonl',[response(13,content=[{'type':'text','text':'UNLINKED_SECRET_SENTINEL'}])])
    write_log(folder/'unrelated-session/subagents/agent-unrelated.jsonl',[response(14,session='unrelated-session')])
    return parent


class SessionAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.store=Store(self.root/'store')

    def import_start(self,path,**kwargs):
        d=import_bundle(self.store,path,**kwargs)
        aid=analyze_dataset(self.store,d['dataset_id'])['analysis_id']
        run=start_session_investigation(self.store,aid,'session-a','Synthetic child collection test')['investigation']
        return d,run

    def test_single_file_collects_linked_nested_logs_and_metadata_without_unrelated_sessions(self):
        d,run=self.import_start(linked_fixture(self.root/'native'))
        self.assertEqual(d['files'],5)
        scope=get_scope(self.store,run)
        self.assertEqual(scope['agent_ids'],['child-a','child-b','main'])
        self.assertEqual(scope['excluded_unlinked_agents'],['unlinked'])
        data=report_data(self.store,run['id'],True,True)
        self.assertEqual(data['agents']['child-a']['role'],'researcher')
        self.assertEqual(data['agents']['missing']['trace_status'],'unavailable')
        self.assertIsNone(data['agents']['missing']['metrics'])
        self.assertEqual(data['main_accounting']['session']['llm_calls']['value'],3)
        self.assertEqual(data['accounting']['session']['llm_calls']['value'],9)
        self.assertEqual(data['agents']['child-a']['metrics']['tool_invocations']['value'],3)
        self.assertEqual(data['accounting']['session']['tool_invocations']['value'],6)
        main_ids=set(data['main_accounting']['turns'][0]['event_ids'])
        self.assertTrue(all(data['sources'][sid]['agent_id']=='main' for sid in main_ids))
        self.assertEqual(data['agents']['child-a']['invocation_ids'],['tool-5'])
        self.assertEqual(data['agents']['child-a']['failure_tool_ids'],['tool-7'])
        html=render_report(data)
        self.assertIn('data-subagent="tool-1"',html)
        self.assertIn('data-agent-events="child-a"',html)
        self.assertIn('Child trace unavailable.',html)
        self.assertIn('Launch acknowledged;',html)
        self.assertNotIn('UNLINKED_SECRET_SENTINEL',html)
        self.assertNotIn('unrelated-session',html)

    def test_renamed_export_finds_only_its_explicit_session_companion(self):
        d,run=self.import_start(linked_fixture(self.root/'renamed',True))
        self.assertEqual(d['files'],5)
        self.assertIn('child-b',get_scope(self.store,run)['agent_ids'])

    def test_parent_only_and_missing_directory_preserve_gaps(self):
        path=linked_fixture(self.root/'native')
        d,run=self.import_start(path,include_subagents=False)
        self.assertEqual(d['files'],1)
        details=get_subagent_details(self.store,run['id'],'tool-1')
        self.assertEqual(details['agents'][0]['trace_status'],'unavailable')
        self.assertIsNone(details['agents'][0]['metrics'])
        self.assertEqual(details['events'],[])
        isolated=write_log(self.root/'isolated/session.log',[human(0),call(1,'Agent'),result(2,'tool-1',meta={'agentId':'elsewhere'})])
        _,other=self.import_start(isolated)
        self.assertEqual(get_subagent_details(self.store,other['id'],'tool-1')['agents'][0]['trace_status'],'unavailable')

    def test_companion_identity_cannot_escape_selected_directory_or_follow_symlink(self):
        outside=self.root/'outside/subagents';outside.mkdir(parents=True)
        write_log(outside/'agent-child.jsonl',[response(10)])
        parent=write_log(self.root/'safe/session.log',[human(0,session='../outside')])
        imported=import_bundle(self.store,parent)
        self.assertEqual(imported['files'],1)
        native=linked_fixture(self.root/'native')
        (native.parent/'session-a/subagents/link.jsonl').symlink_to(outside/'agent-child.jsonl')
        with self.assertRaisesRegex(AnalyzerError,'symlink'):import_bundle(self.store,native)

    def test_child_metadata_endpoint_is_paged_scoped_and_does_not_disclose_text(self):
        _,run=self.import_start(linked_fixture(self.root/'native'))
        before=exposure(self.store,run['id'])['sources']
        page=get_subagent_details(self.store,run['id'],'tool-1',limit=2)
        self.assertEqual(page['total_events'],7)
        self.assertEqual(page['next_offset'],2)
        self.assertNotIn('CHILD_ONLY_SENTINEL',json.dumps(page))
        ids=[];offset=0
        while True:
            p=get_subagent_details(self.store,run['id'],'tool-1',limit=2,offset=offset)
            ids += [e['id'] for e in p['events']]
            if p['next_offset'] is None:break
            offset=p['next_offset']
        self.assertEqual(len(set(ids)),7)
        self.assertEqual(exposure(self.store,run['id'])['sources'],before)
        with self.assertRaises(AnalyzerError):read_investigation_evidence(self.store,run['id'],ids[0])
        self.assertTrue(read_investigation_evidence(self.store,run['id'],ids[0],allow_content=True)['text'])
        with self.assertRaises(AnalyzerError):get_subagent_details(self.store,run['id'],'tool-1',agent_id='unlinked')
        with self.assertRaises(AnalyzerError):get_subagent_details(self.store,run['id'],'foreign-tool')
        service=Service(self.store);self.addCleanup(service.close);service.investigation_id=run['id']
        self.assertEqual(service.call('get_subagent_details',{'investigation_id':run['id'],'tool_id':'tool-5'})['agents'][0]['agent_id'],'child-b')
        metadata=report_data(self.store,run['id'])
        self.assertNotIn('CHILD_ONLY_SENTINEL',render_report(metadata))

    def test_sidecar_alone_can_link_a_captured_child(self):
        path=linked_fixture(self.root/'native')
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        rows[2].pop('toolUseResult')
        write_log(path,rows)
        _,run=self.import_start(path)
        self.assertIn('child-a',get_scope(self.store,run)['agent_ids'])
        self.assertEqual(get_subagent_details(self.store,run['id'],'tool-1')['agents'][0]['role'],'researcher')

    def test_resumed_child_keeps_one_trace_and_distinct_invocations(self):
        path=linked_fixture(self.root/'native')
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        rows.extend([call(92,'Agent',{'resume':'child-a','prompt':'Continue the same child.'}),result(93,'tool-92',meta={'agentId':'child-a'})])
        write_log(path,rows)
        _,run=self.import_start(path)
        data=report_data(self.store,run['id'])
        self.assertEqual(data['agents']['child-a']['parent_invocation_ids'],['tool-1','tool-92'])
        self.assertEqual(data['accounting']['session']['llm_calls']['value'],10)
        self.assertEqual(data['agents']['child-a']['metrics']['llm_calls']['value'],4)

    def test_copied_response_identity_is_not_double_counted_in_agent_metrics(self):
        path=linked_fixture(self.root/'native')
        child=path.parent/'session-a/subagents/agent-child-a.jsonl'
        rows=[json.loads(line) for line in child.read_text().splitlines()]
        rows.append(response(91,mid='msg-90',request='req-90',content=[{'type':'text','text':'Copied provider response.'}]))
        write_log(child,rows)
        _,run=self.import_start(path)
        data=report_data(self.store,run['id'])
        self.assertEqual(len(data['agents']['main']['shared_response_ids']),1)
        self.assertEqual(data['main_accounting']['session']['llm_calls']['value'],2)
        self.assertEqual(data['accounting']['session']['llm_calls']['value'],9)
        self.assertEqual(data['agents']['child-a']['metrics']['llm_calls']['value'],4)

    def test_cli_single_file_collection_matches_python_api(self):
        path=linked_fixture(self.root/'native')
        env={k:v for k,v in os.environ.items() if not k.startswith('ALLY_ANALYZER_')}
        proc=subprocess.run([sys.executable,str(ROOT/'bin/ally-session'),'--data-dir',str(self.root/'cli-store'),'import',str(path)],cwd=self.root,env=env,text=True,capture_output=True,timeout=15)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['files'],5)
