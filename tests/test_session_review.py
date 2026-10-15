"""Review workflow invariants; synthetic records are not a model quality score."""
import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from ally_analyzer import claude_runner
from ally_analyzer.service import Service
from ally_analyzer.session_diagnostics import save_inquiry
from ally_analyzer.session_failures import save_failure_explanation
from ally_analyzer.session_investigation import (finish_investigation, get_investigation_records, records, save_incident)
from ally_analyzer.session_report import report_data, render_report
from ally_analyzer.session_review import (get_investigation_review, latest_draft, save_review_checks, update_workflow)
from ally_analyzer.session_scope import (exposure, get_run, projection, read_investigation_evidence, scope_rows, search_investigation_text)
from ally_analyzer.store import Store
from ally_analyzer.util import AnalyzerError
from tests import test_session_workflow as legacy
from tests import test_session_diagnostics as diagnostics
from tests import test_session_failures as failures
from tests.helpers import call, result


class ReviewWorkflowTests(unittest.TestCase):
    contract_version = 'single-session-v2'
    setUp = legacy.SessionWorkflowTests.setUp
    load = legacy.SessionWorkflowTests.load
    read = legacy.SessionWorkflowTests.read
    read_all = diagnostics.DiagnosticTests.read_all
    inquiry = diagnostics.DiagnosticTests.inquiry
    finish = diagnostics.DiagnosticTests.finish
    incident = diagnostics.DiagnosticTests.incident
    explanation = failures.FailureExplanationTests.explanation

    def prepare(self):
        update_workflow(self.store,self.iid,'investigate')
        self.read_all()
        self.q = save_inquiry(self.store,self.iid,self.inquiry())
        self.f = save_failure_explanation(self.store,self.iid,self.explanation())
        return self.finish()

    def check(self, rid, **changes):
        c={'record_id':rid,'verdict':'supported', 'assessment':'The captured final test result supports the scoped fixture outcome.',
           'causal_support':'not_applicable','evidence_checks':[{'reference':{'source_id':self.ids['event-6']},
           'quote':'Ran 1 test. OK.','supports_or_contradicts':'Supports the stated final check result.'}],
           'remaining_uncertainty':[], 'provenance':{'model':'synthetic-reviewer','skill_version':'synthetic-review'}}
        c.update(changes);return c

    def approve_current(self):
        packet = get_investigation_review(self.store,self.iid)
        ids = [v['id'] for v in packet['records']] + [packet['latest_conclusion_draft']['id']]
        return save_review_checks(self.store,self.iid,[self.check(rid) for rid in ids])

    def test_first_finish_is_immutable_draft_not_completion(self):
        response=self.prepare()
        self.assertTrue(response['review_required'])
        self.assertEqual(response['phase'],'investigate')
        self.assertEqual(get_run(self.store,self.iid)['run_status'],'running')
        self.assertEqual(len(records(self.store,self.iid,'conclusion_draft')),1)
        self.assertIsNone(get_run(self.store,self.iid)['conclusion'])
        with self.assertRaisesRegex(AnalyzerError,'operator-started'):
            save_review_checks(self.store,self.iid,[self.check(self.f['id'])])

    def test_fresh_review_quotes_required_and_completed_when_checked(self):
        self.prepare();update_workflow(self.store,self.iid,'review')
        with self.assertRaisesRegex(AnalyzerError,'reread'):
            self.approve_current()
        self.read_all();self.approve_current()
        done=self.finish()['investigation']
        self.assertEqual(done['run_status'],'completed')
        self.assertEqual(len(records(self.store,self.iid,'conclusion_draft')),1)
        self.assertEqual(len(records(self.store,self.iid,'review_check')),3)

    def test_literal_quotes_reject_reconstructed_shell_syntax(self):
        rows=legacy.session_rows();rows[1]=call(1,args={'command':'LIST="alpha beta"; for item in $LIST; do printf "%s\\n" "$item"; done'})
        self.load(rows);self.prepare();update_workflow(self.store,self.iid,'review');self.read_all()
        check=self.check(self.f['id'],evidence_checks=[{'reference':{'source_id':self.ids['event-1']},
            'quote':'for item in "$LIST"','supports_or_contradicts':'This invented quoting must be rejected.'}])
        with self.assertRaisesRegex(AnalyzerError,'verbatim'): save_review_checks(self.store,self.iid,[check])
        check['evidence_checks'][0]['quote']='for item in $LIST'
        saved=save_review_checks(self.store,self.iid,[check])
        self.assertEqual(saved['saved'][0]['check'],check)
        # Literal checking is not semantic certification of the explanation.
        self.assertIn('not causal reasoning',saved['limitation'])

    def test_revision_requires_new_review_and_preserves_negative_check(self):
        self.prepare();update_workflow(self.store,self.iid,'review');self.read_all()
        self.approve_current()
        rejected=self.check(self.f['id'],verdict='needs_revision',assessment='Synthetic correction needed.')
        save_review_checks(self.store,self.iid,[rejected])
        self.assertIn(self.f['id'],self.finish()['records_needing_review'])
        revised=save_failure_explanation(self.store,self.iid,self.explanation(summary='Synthetic revised explanation.',revision_of=self.f['id']))
        with self.assertRaisesRegex(AnalyzerError,'stale'):
            save_review_checks(self.store,self.iid,[self.check(self.f['id'])])
        self.assertIn(revised['id'],self.finish()['records_needing_review'])
        save_review_checks(self.store,self.iid,[self.check(revised['id'])]);self.finish()
        data=report_data(self.store,self.iid)
        self.assertEqual(len(data['failure_explanations']),2)
        self.assertTrue(any(v['check']==rejected for v in data['review_checks']))
        self.assertIn('Synthetic correction needed.',render_report(data))

    def test_changed_conclusion_needs_new_check(self):
        self.prepare();update_workflow(self.store,self.iid,'review');self.read_all();self.approve_current()
        pending=self.finish(summary='A newly scoped synthetic conclusion.')
        self.assertEqual(pending['records_needing_review'],[pending['draft_id']])
        self.assertEqual(len(records(self.store,self.iid,'conclusion_draft')),2)
        save_review_checks(self.store,self.iid,[self.check(pending['draft_id'])])
        done=self.finish(summary='A newly scoped synthetic conclusion.')
        self.assertEqual(done['investigation']['summary'],'A newly scoped synthetic conclusion.')

    def test_partial_is_not_unavailable_when_work_remains_open(self):
        self.prepare();update_workflow(self.store,self.iid,'review');self.read_all()
        q=save_inquiry(self.store,self.iid,self.inquiry(status='open',answer='Comparison still needs investigation.',
             next_source_ids=[self.ids['event-6']],revision_of=self.q['id']))
        params=dict(run_status='partial',stop_basis='evidence_unavailable',unresolved_questions=['An available comparison is unfinished.'])
        self.finish(**params);self.approve_current()
        self.assertTrue(self.finish(**params)['continue_required'])
        params['stop_basis']='investigator_choice';self.finish(**params);self.approve_current()
        self.assertTrue(self.finish(**params)['continue_required'])
        self.assertEqual(get_run(self.store,self.iid)['run_status'],'running')

    def test_unavailable_closed_question_can_complete_without_success_claim(self):
        self.prepare();update_workflow(self.store,self.iid,'review');self.read_all()
        save_inquiry(self.store,self.iid,self.inquiry(status='unavailable',answer='The independent external run is not captured.',
            references=[],missing_evidence=['External run result'],revision_of=self.q['id']))
        params=dict(conclusion='insufficient_evidence',stop_basis='evidence_unavailable',unresolved_questions=['External result unavailable.'])
        self.finish(**params);self.approve_current()
        self.assertEqual(self.finish(**params)['investigation']['run_status'],'completed')

    def test_known_available_source_cannot_be_dropped_to_close_question(self):
        first=save_inquiry(self.store,self.iid,self.inquiry(status='open',answer='Result unread.',next_source_ids=[self.ids['event-6']]))
        with self.assertRaisesRegex(AnalyzerError,'remain unread'):
            save_inquiry(self.store,self.iid,self.inquiry(status='unavailable',references=[],missing_evidence=['Claimed absent.'],revision_of=first['id']))

    def test_incident_revision_retains_history_without_duplicate_active_finding(self):
        self.read_all();first=save_incident(self.store,self.iid,self.incident())
        second=save_incident(self.store,self.iid,self.incident(title='Revised synthetic finding',revision_of=first['id']))
        data=report_data(self.store,self.iid)
        self.assertEqual([v['id'] for v in data['incidents']],[second['id']])
        self.assertEqual(len(data['incident_history']),2)
        with self.assertRaisesRegex(AnalyzerError,'current version'):
            save_incident(self.store,self.iid,self.incident(title='Stale branch',revision_of=first['id']))

    def test_search_history_and_successful_reads_are_navigation_not_absence(self):
        rows=legacy.session_rows()+[call(10,name='Read',args={'file_path':'background-output.txt'}),
              result(11,'tool-10','Worker exceeded memory limit. Suite failed to start.')]
        self.load(rows);update_workflow(self.store,self.iid,'investigate')
        found=search_investigation_text(self.store,self.iid,'heap exhausted',allow_content=True)
        self.assertEqual(found['matches'],[])
        packet=get_investigation_review(self.store,self.iid,limit=1)
        self.assertTrue(packet['search_history'][0]['reached_end_of_scope'])
        self.assertEqual(packet['search_history'][0]['query'],'heap exhausted')
        self.assertIn(self.ids['event-11'],json.dumps(packet['recent_main_tools']))
        found=search_investigation_text(self.store,self.iid,'memory',allow_content=True)
        self.assertEqual(found['matches'][0]['source_id'],self.ids['event-11'])

    def test_scoped_service_routes_review_but_not_operator_transition(self):
        self.prepare()
        service=Service(self.store,allow_content=False)
        try:
            packet=service.call('get_investigation_review',{'investigation_id':self.iid,'limit':1})
            self.assertEqual(packet['total_records'],2);self.assertEqual(packet['next_offset'],1)
            self.assertEqual(packet['workflow']['phase'],'investigate')
            with self.assertRaises(AnalyzerError): service.call('update_workflow',{'investigation_id':self.iid,'phase':'review'})
        finally: service.close()

    def test_managed_runner_two_hosts_exact_outputs_and_bounded_budget(self):
        fixture=self.root/'source-0.jsonl';work=self.root/'managed'
        def fake_host(command,stage,env,timeout):
            self.store=Store(env['ALLY_ANALYZER_HOME']);self.iid=env['ALLY_ANALYZER_INVESTIGATION_ID'];self.run=get_run(self.store,self.iid)
            self.ids={json.loads(r['raw']).get('uuid'):r['id'] for r in scope_rows(self.store,self.run)}
            calls=[]
            def emit(name,**inputs):
                calls.append({'type':'assistant','message':{'content':[{'type':'tool_use','id':'synthetic-'+str(len(calls)),
                    'name':name if name=='Skill' else 'mcp__plugin_ally-session-analyzer_ally-session-analyzer__'+name,'input':inputs}]}})
            emit('Skill',skill='ally-session-analyzer:write-report')
            self.read_all()
            if stage.name=='investigate':
                # Synthetic host-authored citations exercise the production
                # requirement; the runner must never insert these for a model.
                captions={self.ids['event-'+str(i)]:text for i,text in [
                    (0,'The request asks for a negative test followed by repair.'),
                    (1,'The first invocation runs the fixture test.'),
                    (2,'The initial test reports a failure.'),
                    (3,'The edit replaces the broken fixture value.'),
                    (4,'The editor reports the replacement succeeded.'),
                    (5,'The next invocation repeats the fixture test.'),
                    (6,'The check passes after the fixture edit.'),
                    (8,'The user asks for an explanation of the change.'),
                    (9,'The assistant states that the fixture was repaired.')]}
                def authored(value):
                    if isinstance(value,dict):
                        if 'source_id' in value:value['explanation']=captions[value['source_id']]
                        for child in list(value.values()):authored(child)
                    elif isinstance(value,list):
                        for child in value:authored(child)
                    return value
                from ally_analyzer.session_requirements import save_requirement_map
                mapped={'scope':'Synthetic runner contract fixture; semantic diagnosis is tested separately.','inventory_status':'partial',
                        'requirements':[],'context_only':[],'limitations':['This fake host exercises transport only.'],
                        'provenance':{'model':'synthetic-test','skill_version':'runner-fixture'}}
                save_requirement_map(self.store,self.iid,mapped);emit('save_requirement_map',investigation_id=self.iid,requirement_map=mapped)
                q=authored(self.inquiry());save_inquiry(self.store,self.iid,q);emit('save_inquiry',investigation_id=self.iid,inquiry=q)
                f=authored(self.explanation());save_failure_explanation(self.store,self.iid,f);emit('save_failure_explanation',investigation_id=self.iid,explanation=f)
                self.finish(synopsis=authored({'text':'The request asks for a negative test, repair and explanation.',
                    'references':[{'source_id':self.ids['event-0']}],'limitations':[]}),
                    observed_outcome=authored({'text':'The final fixture check passed.','evidence_class':'recorded_observation',
                    'references':[{'source_id':self.ids['event-6']}],'limitations':[]}))
                candidate=latest_draft(self.store,self.iid)['conclusion'];emit('finish_investigation',investigation_id=self.iid,**candidate)
            else:
                packet=get_investigation_review(self.store,self.iid)
                checks=[]
                for v in packet['records']+[packet['latest_conclusion_draft']]:
                    plan=v['semantic_review']
                    checks.append(self.check(v['id'],semantic_checks=[{'aspect':aspect,'verdict':'consistent',
                        'assessment':'Synthetic transport fixture; no claim of semantic evaluation.',
                        'related_record_ids':[plan['current_requirement_map_id']] if aspect=='opening_requirement_consistency' and plan['current_requirement_map_id'] else []}
                        for aspect in plan['required_aspects']]))
                save_review_checks(self.store,self.iid,checks);emit('save_review_checks',investigation_id=self.iid,checks=checks)
                candidate=latest_draft(self.store,self.iid)['conclusion']
                finish_investigation(self.store,self.iid,**candidate);emit('finish_investigation',investigation_id=self.iid,**candidate)
            rows=[{'type':'system','subtype':'init','model':'synthetic-test'}]+calls+[{'type':'result','subtype':'success','is_error':False,'result':'Exact synthetic host answer.','total_cost_usd':0.1}]
            (stage/'transcript.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));(stage/'stderr.log').write_text('')
            return {'exit_code':0,'host_error':None,'timed_out':False}
        with patch.object(claude_runner,'run_host',side_effect=fake_host),contextlib.redirect_stdout(io.StringIO()):
            code=claude_runner.main(['--source',str(fixture),'--work-dir',str(work),'--allow-content','--max-budget-usd','1'])
        self.assertEqual(code,0)
        audit=json.loads((work/'audit.json').read_text())
        self.assertTrue(audit['origin_and_transport_checks_passed'])
        self.assertTrue(audit['host_completed_investigation'])
        self.assertEqual([s['phase'] for s in audit['stages']],['investigate','review'])
        self.assertAlmostEqual(audit['stages'][0]['budget_usd'],0.6)
        self.assertAlmostEqual(audit['stages'][1]['budget_usd'],0.9)
        self.assertEqual((work/'review/claude-answer.md').read_text(),'Exact synthetic host answer.')
        self.assertTrue((work/'tested-plugin.zip').is_file())

    def test_managed_runner_unfinished_hosts_preserve_partial_and_unknown_usage(self):
        work=self.root/'unfinished'
        def stopped_host(command,stage,env,timeout):
            (stage/'transcript.jsonl').write_text(json.dumps({'type':'system','subtype':'init','model':'synthetic-test'})+'\n')
            (stage/'stderr.log').write_text('Synthetic interrupted host.')
            return {'exit_code':None,'host_error':None,'timed_out':True}
        with patch.object(claude_runner,'run_host',side_effect=stopped_host),contextlib.redirect_stdout(io.StringIO()):
            code=claude_runner.main(['--source',str(self.root/'source-0.jsonl'),'--work-dir',str(work),'--max-budget-usd','1'])
        audit=json.loads((work/'audit.json').read_text())
        data=json.loads((work/'claude-investigation.json').read_text())
        self.assertEqual(code,1)
        self.assertEqual(audit['run_status'],'partial')
        self.assertFalse(audit['host_completed_investigation'])
        self.assertAlmostEqual(audit['stages'][1]['budget_usd'],0.4)
        self.assertIsNone(data['investigation']['analyzer_usage']['cost_usd'])
        self.assertEqual(data['investigation']['stop_basis'],'external_limit')
        self.assertEqual(data['conclusion_drafts'],[])
        self.assertTrue((work/'claude-investigation.html').exists())
        self.assertLessEqual(len(audit['stages']),3)

    def test_managed_runner_does_not_review_an_authentication_failure(self):
        work=self.root/'authentication-failure'
        message='Failed to authenticate: OAuth session expired and could not be refreshed'
        def failed_host(command,stage,env,timeout):
            rows=[{'type':'system','subtype':'init','model':'synthetic-host'},
                  {'type':'result','subtype':'success','is_error':True,'terminal_reason':'api_error',
                   'result':message,'total_cost_usd':0}]
            (stage/'transcript.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            (stage/'stderr.log').write_text('')
            return {'exit_code':1,'host_error':None,'timed_out':False}
        with patch.object(claude_runner,'run_host',side_effect=failed_host) as host,contextlib.redirect_stdout(io.StringIO()):
            code=claude_runner.main(['--source',str(self.root/'source-0.jsonl'),'--work-dir',str(work)])
        self.assertEqual(code,1);self.assertEqual(host.call_count,1)
        audit=json.loads((work/'audit.json').read_text())
        data=json.loads((work/'claude-investigation.json').read_text())
        self.assertEqual(audit['run_status'],'failed')
        self.assertFalse(audit['independent_review_host_started'])
        self.assertEqual(data['investigation']['stop_basis'],'external_limit')
        self.assertIn(message,data['investigation']['stop_reason'])
        self.assertEqual((work/'claude-answer.md').read_text(),message)
        self.assertEqual(audit['saved_incidents'],0)

    def test_host_cannot_append_parent_pipe_to_explicit_prompt(self):
        import os
        import subprocess
        import sys
        work=self.root/'stdin-boundary';work.mkdir()
        child="import json,sys; print(json.dumps({'stdin':sys.stdin.read(),'prompt':sys.argv[1]}))"
        launch=("import os,sys; from pathlib import Path; "
                "from ally_analyzer.claude_runner import run_host; "
                "result=run_host([sys.executable,'-c',"+repr(child)+",'Explicit approved prompt'],"
                "Path("+repr(str(work))+"),os.environ.copy(),5); "
                "assert result['exit_code']==0, result")
        outer=subprocess.run([sys.executable,'-c',launch],
            cwd=Path(__file__).resolve().parents[1],env=os.environ.copy(),
            input='UNRELATED_PARENT_PIPE_SENTINEL',text=True,capture_output=True,timeout=10)
        self.assertEqual(outer.returncode,0,outer.stderr)
        received=json.loads((work/'transcript.jsonl').read_text())
        self.assertEqual(received,{'stdin':'','prompt':'Explicit approved prompt'})

    def test_review_can_record_a_negative_check_on_a_superseded_version(self):
        self.prepare();update_workflow(self.store,self.iid,'review');self.read_all()
        revised=save_failure_explanation(self.store,self.iid,self.explanation(summary='A revision.',revision_of=self.f['id']))
        check=self.check(self.f['id'],verdict='needs_revision',assessment='The original omitted a material limit.')
        saved=save_review_checks(self.store,self.iid,[check])
        self.assertEqual(saved['saved'][0]['check'],check)
        with self.assertRaisesRegex(AnalyzerError,'stale'):
            save_review_checks(self.store,self.iid,[self.check(self.f['id'])])

    def test_all_main_requests_must_be_mapped_without_requiring_full_trajectory(self):
        update_workflow(self.store,self.iid,'investigate')
        self.read(self.ids['event-0'])
        packet=get_investigation_review(self.store,self.iid)
        self.assertEqual(packet['request_coverage']['main_requests'],2)
        self.assertEqual(packet['request_coverage']['fully_read'],1)
        self.assertIn('unmapped_main_requests',{x['code'] for x in packet['diagnostics']['blocking_issues']})
        self.read(self.ids['event-8'])
        packet=get_investigation_review(self.store,self.iid)
        self.assertEqual(packet['request_coverage']['unread_requests'],[])
        self.assertLess(len(exposure(self.store,self.iid)['sources']),len(self.ids))

    def test_tool_audit_preserves_rejected_attempt_and_does_not_assume_execution(self):
        transcript=self.root/'policy.jsonl'
        call={'id':'bad','name':'nonexistent_reader','input':{}}
        result={'type':'tool_result','tool_use_id':'bad','is_error':True,
                'content':'<tool_use_error>Error: No such tool available: nonexistent_reader</tool_use_error>'}
        transcript.write_text(json.dumps({'type':'user','message':{'content':[result]}})+'\n')
        audit=claude_runner.audit_tool_policy([call],transcript,[])
        self.assertFalse(audit['allowed_calls_only'])
        self.assertTrue(audit['executed_calls_within_policy'])
        self.assertEqual(len(audit['rejected_unknown_tool_attempts']),1)
        result['content']='Some other error, not evidence that execution was prevented.'
        transcript.write_text(json.dumps({'type':'user','message':{'content':[result]}})+'\n')
        self.assertFalse(claude_runner.audit_tool_policy([call],transcript,[])['executed_calls_within_policy'])


if __name__=='__main__':unittest.main()
