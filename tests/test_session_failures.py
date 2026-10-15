"""Synthetic contract fixtures. These are not model quality evaluations."""
import json
import re
import unittest

from ally_analyzer.service import Service
from ally_analyzer.session_failures import (active_explanations, get_recorded_failures, save_failure_explanation)
from ally_analyzer.session_investigation import get_investigation_records, get_session_overview
from ally_analyzer.session_report import report_data, render_report
from ally_analyzer.session_scope import exposure, start_session_investigation
from ally_analyzer.util import AnalyzerError
from tests import test_session_workflow as legacy
from tests.helpers import call, result


class FailureExplanationTests(unittest.TestCase):
    contract_version = 'single-session-v2'
    setUp = legacy.SessionWorkflowTests.setUp
    load = legacy.SessionWorkflowTests.load
    read = legacy.SessionWorkflowTests.read

    def explanation(self, **changes):
        e = {'tool_id':'tool-1', 'status':'explained',
             'summary':'The agent ran the requested negative test. It returned a failed assertion.',
             'resolution':'recovered', 'follow_up':'After the fixture edit, the same test passed.',
             'references':[{'source_id':self.ids['event-0']},{'source_id':self.ids['event-1']},{'source_id':self.ids['event-2']}],
             'recovery_references':[{'source_id':self.ids['event-5']},{'source_id':self.ids['event-6']}],
             'limitations':[], 'provenance':{'model':'synthetic-test','skill_version':'failure-contract-fixture'}}
        e.update(changes)
        return e

    def read_all(self):
        for sid in self.ids.values(): self.read(sid, max_chars=12000)

    def test_failure_listing_is_metadata_only_scoped_and_pageable(self):
        rows = legacy.session_rows() + [call(10),result(11,'tool-10','Second attempt failed.',True)]
        self.load(rows)
        before = exposure(self.store,self.iid)['sources']
        first = get_recorded_failures(self.store,self.iid,limit=1)
        second = get_recorded_failures(self.store,self.iid,limit=1,offset=first['next_offset'])
        self.assertEqual([first['items'][0]['tool_id'],second['items'][0]['tool_id']],['tool-1','tool-10'])
        self.assertEqual(first['total'],2)
        self.assertIsNone(second['next_offset'])
        self.assertNotIn('Second attempt failed.',json.dumps(second))
        self.assertEqual(exposure(self.store,self.iid)['sources'],before)
        self.assertEqual(first['items'][0]['turns'][0]['request_source_id'],self.ids['event-0'])
        self.assertEqual([t['tool_id'] for t in first['items'][0]['next_tools']],['tool-3','tool-5'])
        self.assertEqual(set(first['items'][0]['evidence_roles'].values()),{'tool_call','tool_result'})
        self.assertEqual(first['coverage']['not_investigated'],2)

    def test_unread_or_unrelated_failure_evidence_cannot_support_explanation(self):
        with self.assertRaisesRegex(AnalyzerError,'Read every cited'): save_failure_explanation(self.store,self.iid,self.explanation())
        self.read_all()
        wrong = self.explanation(references=[{'source_id':self.ids['event-5']},{'source_id':self.ids['event-6']}])
        with self.assertRaisesRegex(AnalyzerError,'own inspected'): save_failure_explanation(self.store,self.iid,wrong)
        for tool in ('tool-5','not-scoped'):
            with self.assertRaisesRegex(AnalyzerError,'recorded failure'): save_failure_explanation(self.store,self.iid,self.explanation(tool_id=tool))

    def test_recovery_requires_later_primary_success_not_original_failure_or_narration(self):
        self.read_all()
        for sid in ('event-2','event-9'):
            with self.assertRaises(AnalyzerError):
                save_failure_explanation(self.store,self.iid,self.explanation(recovery_references=[{'source_id':self.ids[sid]}]))
        saved = save_failure_explanation(self.store,self.iid,self.explanation())
        self.assertEqual(saved['explanation'],self.explanation())

    def test_earlier_success_is_not_recovery(self):
        rows=legacy.session_rows()
        rows[2]=result(2,'tool-1','OK');rows[6]=result(6,'tool-5','Failed',True)
        self.load(rows)
        self.read_all()
        e=self.explanation(tool_id='tool-5',references=[{'source_id':self.ids['event-5']},{'source_id':self.ids['event-6']}],
                           recovery_references=[{'source_id':self.ids['event-2']}])
        with self.assertRaisesRegex(AnalyzerError,'later successful'):save_failure_explanation(self.store,self.iid,e)

    def test_exact_revision_history_and_foreign_revision_are_preserved(self):
        self.read_all()
        first = save_failure_explanation(self.store,self.iid,self.explanation())
        self.assertEqual(save_failure_explanation(self.store,self.iid,self.explanation())['id'],first['id'])
        revised=self.explanation(summary='A corrected synthetic description.')
        with self.assertRaisesRegex(AnalyzerError,'revise the current'):save_failure_explanation(self.store,self.iid,revised)
        revised['revision_of']=first['id']
        second=save_failure_explanation(self.store,self.iid,revised)
        with self.assertRaisesRegex(AnalyzerError,'revise the current'):save_failure_explanation(self.store,self.iid,self.explanation(revision_of=first['id']))
        values=get_investigation_records(self.store,self.iid,'failure_explanations')['items']
        self.assertEqual(len(values),2)
        self.assertEqual(active_explanations(values)['tool-1']['id'],second['id'])
        new=start_session_investigation(self.store,self.aid,'session-a','Separate run')['investigation']['id']
        with self.assertRaisesRegex(AnalyzerError,'revise the current'):save_failure_explanation(self.store,new,revised)

    def test_partial_citations_unknown_and_insufficient_evidence_need_limits(self):
        input_page=self.read(self.ids['event-1'])
        page=self.read(self.ids['event-2'],max_chars=6)
        ref={'source_id':self.ids['event-2'],'text_sha256':page['text_sha256'],'start_char':0,'end_char':6}
        e=self.explanation(references=[{'source_id':input_page['source_id']},ref],status='insufficient_evidence',
                           resolution='unknown',recovery_references=[],follow_up='Later results have not been inspected.')
        with self.assertRaisesRegex(AnalyzerError,'material evidence gap'):save_failure_explanation(self.store,self.iid,e)
        e['limitations']=['The original result is only partially inspected.']
        saved=save_failure_explanation(self.store,self.iid,e)
        self.assertEqual(saved['evidence_review']['original_sources_not_fully_inspected'],[self.ids['event-2']])
        coverage=get_session_overview(self.store,self.iid)['failure_explanations']
        self.assertEqual((coverage['insufficient_evidence'],coverage['not_investigated']),(1,0))
        ref['end_char']=8
        e['revision_of']=saved['id']
        with self.assertRaisesRegex(AnalyzerError,'Read every cited'):save_failure_explanation(self.store,self.iid,e)

    def test_available_follow_up_cannot_be_skipped_in_an_explained_attempt(self):
        self.read_all()
        e=self.explanation(resolution='unknown',recovery_references=[],limitations=['Follow-up not investigated.'])
        with self.assertRaisesRegex(AnalyzerError,'Available follow-up'):save_failure_explanation(self.store,self.iid,e)
        e['status']='insufficient_evidence'
        saved=save_failure_explanation(self.store,self.iid,e)
        self.assertEqual(saved['explanation']['status'],'insufficient_evidence')

    def test_export_is_stable_when_projection_cache_changes_dictionary_order(self):
        from ally_analyzer.session_report import export_session_investigation
        self.read_all();save_failure_explanation(self.store,self.iid,self.explanation())
        self.load(legacy.session_rows()+[legacy.human(20,'A previously unread request.')])
        path=self.root/'first.json'
        export_session_investigation(self.store,self.iid,path,'json',True,True)
        first=json.loads(path.read_text())
        second=report_data(self.store,self.iid,True,True)
        self.assertEqual(first,second)
        self.assertEqual(render_report(first),render_report(second))

    def test_report_preserves_authored_text_without_creating_explanations_or_recommendations(self):
        baseline=report_data(self.store,self.iid,True,True)
        self.assertIn('No explanation was saved for this attempt.',render_report(baseline))
        self.read_all()
        e=self.explanation(summary='Literal <script> & \"quoted\" text.\nAnother sentence.')
        save_failure_explanation(self.store,self.iid,e)
        data=report_data(self.store,self.iid,True,True); html=render_report(data)
        self.assertEqual(data['recommendations'],[])
        self.assertEqual(data['turn_patterns'],baseline['turn_patterns'])
        self.assertIn('Literal &lt;script&gt; &amp; &quot;quoted&quot; text.\nAnother sentence.',html)
        embedded=json.loads(re.search(r'id="report-data">(.*?)</script>',html,re.S).group(1))
        self.assertEqual(embedded,data)
        self.assertEqual(embedded['failure_explanations'][0]['explanation'],e)
        self.assertIn('Original tool input and result',html)
        self.assertEqual(data['failure_explanation_coverage']['explained'],1)
        # A metadata export preserves explanations without exposing extra source text.
        metadata=report_data(self.store,self.iid)
        self.assertEqual(metadata['failure_explanations'][0]['explanation'],e)
        self.assertTrue(all('text' not in source for source in metadata['sources'].values()))

    def test_bound_mcp_routes_new_tools_and_refuses_other_investigation(self):
        service=Service(self.store,allow_content=True); self.addCleanup(service.close)
        service.investigation_id=self.iid
        first=service.call('get_recorded_failures',{'investigation_id':self.iid})
        self.assertEqual(first['total'],1)
        self.read_all()
        result=service.call('save_failure_explanation',{'investigation_id':self.iid,'explanation':self.explanation()})
        self.assertEqual(result['explanation'],self.explanation())
        with self.assertRaisesRegex(AnalyzerError,'different investigation'):
            service.call('get_recorded_failures',{'investigation_id':'another-run'})
