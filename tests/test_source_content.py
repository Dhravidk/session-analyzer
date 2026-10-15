"""Captured thinking is not visible speech, executed work or extra output usage."""
import copy
import json
import re
import unittest

from ally_analyzer.source_content import source_content
from ally_analyzer.trajectory import trajectory_text
from ally_analyzer.session_diagnostics import inspected_reference, record_role
from ally_analyzer.session_investigation import accounting, save_incident
from ally_analyzer.session_report import report_data, render_report
from ally_analyzer.util import AnalyzerError
from tests import test_session_diagnostics as fixture
from tests.helpers import response, usage


class SourceContentTests(unittest.TestCase):
    contract_version='single-session-v2'
    setUp=fixture.DiagnosticTests.setUp
    load=fixture.DiagnosticTests.load
    read=fixture.DiagnosticTests.read

    def test_empty_missing_redacted_and_unsupported_thinking_are_distinct(self):
        cases=[({'type':'thinking','thinking':'','signature':'opaque'},'empty'),
               ({'type':'thinking'},'missing'),({'type':'thinking','thinking':{}},'unsupported'),
               ({'type':'redacted_thinking','data':'opaque'},'provider_redacted')]
        for block,status in cases:
            with self.subTest(status=status):
                record=response(1,content=[block]);info=source_content(record,True)
                self.assertEqual(info['kind'],'thinking')
                self.assertEqual(info['blocks'][0]['status'],status)
                self.assertEqual(info['thinking_text'],[])
                self.assertEqual(record_role(record),'assistant_thinking')
                self.assertNotIn('opaque',json.dumps(info))

    def test_retained_thinking_is_masked_for_local_export_but_not_model_evidence(self):
        record=response(1,content=[{'type':'thinking','thinking':'Check /Users/alice/project then person@example.com.','signature':'opaque-signature'}])
        text,disclosure=trajectory_text(record)
        self.assertEqual(text,'')
        self.assertEqual(disclosure['content_metadata']['thinking_text'],[])
        info=source_content(record,True)
        self.assertIn('/[USER]/project',info['thinking_text'][0]['text'])
        self.assertNotIn('alice',json.dumps(info));self.assertNotIn('person@example.com',json.dumps(info))
        self.assertFalse(info['thinking_text'][0]['evidence_projection'])
        self.assertEqual(info['blocks'][0]['status'],'omitted_by_policy')

    def test_mixed_text_and_thinking_keeps_visible_text_and_legacy_hash_input(self):
        record=response(1,content=[{'type':'thinking','thinking':'Synthetic planning text.'},{'type':'text','text':'Actual response.'}])
        current,disclosure=trajectory_text(record)
        previous,old_disclosure=trajectory_text(record,'trajectory-text-v2')
        self.assertEqual(current,previous);self.assertEqual(current,'Actual response.')
        self.assertIn('media_thinking_or_unsupported_block',old_disclosure['omitted_categories'])
        self.assertNotIn('media_thinking_or_unsupported_block',disclosure['omitted_categories'])
        self.assertEqual(disclosure['content_metadata']['kind'],'mixed')
        self.assertEqual(record_role(record),'assistant_statement')

    def test_media_and_unknown_shapes_do_not_get_a_thinking_label(self):
        for content,status in [([{'type':'image'}],'omitted_by_policy'),([{'type':'future_block'}],'unsupported'),
                               ([{'type':{}}],'unsupported'),([], 'empty'),(None,'missing'),(12,'unsupported')]:
            record=response(1);record['message']['content']=content
            info=source_content(record)
            self.assertEqual(info['blocks'][0]['status'],status)
            self.assertEqual(record_role(record),'assistant_record')

        nested=response(8,content=[{'type':'tool_use','id':'tool-8','name':'Example',
                                  'input':{'environment':{'secret':'do-not-export'},
                                           'nested':[{'type':'image','data':'opaque-image'}]}}])
        nested['environment']={'token':'do-not-export'}
        projected,disclosure=trajectory_text(nested)
        info=disclosure['content_metadata']
        self.assertEqual({item['type'] for item in info['projection_omissions']},{'environment','image'})
        self.assertTrue(all(item['reason'] and item['path'] for item in info['projection_omissions']))
        self.assertNotIn('do-not-export',projected+json.dumps(info))
        self.assertNotIn('opaque-image',projected+json.dumps(info))

    def test_empty_thinking_cannot_support_a_finding_even_after_a_read(self):
        from tests.test_session_workflow import session_rows
        rows=session_rows();rows[2]=response(2,content=[{'type':'thinking','thinking':''}])
        self.load(rows)
        read=self.read(self.ids['event-2'])
        self.assertEqual(read['text'],'')
        ref={'source_id':self.ids['event-2']}
        self.assertFalse(inspected_reference(self.store,self.run,ref))
        incident=fixture.DiagnosticTests.incident(self)
        with self.assertRaisesRegex(AnalyzerError,'empty or omitted excerpt'):
            save_incident(self.store,self.iid,incident)

        rows[2]=response(2,content=[{'type':'text','text':' \n\t'}])
        self.load(rows);self.read(self.ids['event-2'])
        self.assertFalse(inspected_reference(self.store,self.run,{'source_id':self.ids['event-2']}))
        with self.assertRaisesRegex(AnalyzerError,'empty or omitted excerpt'):
            save_incident(self.store,self.iid,fixture.DiagnosticTests.incident(self))

    def test_response_usage_is_shared_and_counted_once_with_thinking_frames(self):
        from tests.test_session_workflow import human
        first=response(1,u=usage(output=30,thinking=20),content=[{'type':'thinking','thinking':''}])
        second=response(2,mid=first['message']['id'],request=first['requestId'],block=1,u=usage(output=40,thinking=20),content=[{'type':'text','text':'Result statement.'}])
        self.load([human(0),first,second])
        before=copy.deepcopy(accounting(self.store,self.run))
        data=report_data(self.store,self.iid,True,True)
        a,b=(data['sources'][self.ids['event-'+str(i)]] for i in (1,2))
        self.assertEqual(a['response_ids'],b['response_ids'])
        counted=data['response_usage'][a['response_ids'][0]]
        self.assertEqual(counted['tokens']['output_tokens'],40)
        self.assertEqual(counted['tokens']['thinking_tokens'],20)
        self.assertEqual(counted['thinking_tokens_status'],'reported')
        self.assertEqual(len(counted['evidence']),2)
        self.assertEqual(data['accounting'],before)
        self.assertEqual(data['accounting']['session']['llm_calls']['value'],1)
        self.assertEqual(data['accounting']['session']['completion_tokens']['value'],40)
        self.assertEqual(a['timestamp'],'2026-09-01T12:00:01.000000+00:00')
        self.assertEqual(a['role'],'assistant_thinking')

        invalid=response(3,u=usage(output=40,thinking=80),content=[{'type':'thinking','thinking':''}])
        self.load([human(0),invalid])
        data=report_data(self.store,self.iid,True,True)
        counted=next(iter(data['response_usage'].values()))
        self.assertIsNone(counted['tokens']['thinking_tokens'])
        self.assertEqual(counted['thinking_tokens_status'],'unavailable')
        self.assertIn('Thinking count exceeds inclusive output count',counted['warnings'])

    def test_local_export_preserves_prose_and_respects_source_text_opt_in(self):
        from tests.test_session_workflow import human
        self.load([human(0),response(1,content=[{'type':'thinking','thinking':'Synthetic local planning text.'}])])
        private=report_data(self.store,self.iid,False,False)
        exported=report_data(self.store,self.iid,True,True)
        self.assertEqual(private['sources'][self.ids['event-1']]['content_metadata']['thinking_text'],[])
        source=exported['sources'][self.ids['event-1']]
        self.assertEqual(source['text'],'')
        self.assertEqual(source['content_metadata']['thinking_text'][0]['text'],'Synthetic local planning text.')
        original=copy.deepcopy(exported)
        rendered=render_report(exported)
        embedded=json.loads(re.search(r'id="report-data">(.*?)</script>',rendered,re.S).group(1))
        self.assertEqual(original,exported);self.assertEqual(embedded,original)


if __name__=='__main__':unittest.main()
