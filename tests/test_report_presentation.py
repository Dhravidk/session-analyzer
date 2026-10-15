"""Report data integrity and unknown-state regressions; UI behavior is checked in-browser."""
import copy
import json
import re
import unittest
from ally_analyzer.session_report import render_report, report_data, analyzer_metrics, token_breakdown, command_request, request_preview
from tests import test_session_diagnostics as fixture


class ReportPresentationTests(unittest.TestCase):
    setUp=fixture.DiagnosticTests.setUp
    load=fixture.DiagnosticTests.load
    contract_version='single-session-v2'

    def test_presentation_preserves_every_embedded_source_and_metric(self):
        data=report_data(self.store,self.iid,True,True)
        original=copy.deepcopy(data)
        html=render_report(data)
        payload=json.loads(re.search(r'<script type="application/json" id="report-data">(.*?)</script>',html,re.S).group(1))
        self.assertEqual(payload,original)
        self.assertEqual(data,original)
        self.assertIn('class="source-inspector"',html)
        self.assertIn('id="source-panels"',html)
        self.assertNotIn('Webcore migration session',html)

    def test_complete_token_components_in_main_and_each_turn(self):
        data=report_data(self.store,self.iid)
        html=render_report(data)
        for key in ('prompt_tokens','uncached_input_tokens','cache_creation_tokens','cached_tokens','completion_tokens'):
            self.assertGreaterEqual(html.count('data-metric="'+key+'"'),len(data['accounting']['turns'])+1)
        self.assertIn('Input total includes uncached input, cache write and cache read.',html)
        self.assertIn('Recorded duration (s)',html)
        self.assertIn('Observed span (s)',html)

    def test_partial_tokens_show_unknown_and_known_subtotal_without_coercion(self):
        metrics={'prompt_tokens':{'value':None,'known_subtotal':123,'known':1,'eligible':3}}
        html=token_breakdown(metrics,'Synthetic partial')
        self.assertIn('<strong>Unknown</strong>',html)
        self.assertIn('Known subtotal 123',html)
        self.assertIn('1/3 recorded',html)
        self.assertNotIn('<strong>0</strong>',html)

    def test_analyzer_usage_does_not_sum_duplicate_nested_iterations(self):
        run={'analyzer_usage':{'usage':[{'phase':'review','usage':{
            'input_tokens':2,'cache_creation_input_tokens':3,'cache_read_input_tokens':5,'output_tokens':7,
            'iterations':[{'input_tokens':9999,'output_tokens':9999}]}}]}}
        html=analyzer_metrics(run)
        self.assertIn('<strong>10</strong>',html)
        self.assertIn('<strong>2</strong>',html)
        self.assertIn('<strong>3</strong>',html)
        self.assertIn('<strong>5</strong>',html)
        self.assertIn('<strong>7</strong>',html)
        self.assertNotIn('<strong>9999</strong>',html)
        run['analyzer_usage']['usage'][0]['usage'].pop('cache_read_input_tokens')
        self.assertIn('<strong>Unknown</strong>',analyzer_metrics(run))

    def test_stored_prose_and_unknown_status_are_not_rewritten(self):
        data=report_data(self.store,self.iid,True,True)
        data['investigation'].update(run_status='partial',stop_reason='Synthetic checkpoint: waiting on evidence.',
                                    summary='Exact wording <with> punctuation. No claim of completion.')
        html=render_report(data)
        self.assertIn('Incomplete investigation',html)
        self.assertIn('Synthetic checkpoint: waiting on evidence.',html)
        self.assertIn('Exact wording &lt;with&gt; punctuation. No claim of completion.',html)
        self.assertIn('No recommendations saved. The investigation is incomplete.',html)

    def test_icons_and_csp_remain_offline_and_text_stays_escaped(self):
        data=report_data(self.store,self.iid)
        data['investigation']['title']='</title><script>NOT_EXECUTABLE</script>'
        html=render_report(data)
        self.assertIn('img-src data:',html)
        self.assertIn('Feather icons v4.29.1',html)
        self.assertIn('MIT License',html)
        self.assertNotIn('<script>NOT_EXECUTABLE</script>',html)
        self.assertNotIn('<script src=',html)

    def test_command_fields_preserve_full_source_findings_and_payload(self):
        from ally_analyzer.session_investigation import save_incident
        save_incident(self.store,self.iid,fixture.DiagnosticTests.incident(self))
        data=report_data(self.store,self.iid,True,True)
        turn=data.get('main_accounting',data['accounting'])['turns'][0]
        source=data['sources'][turn['request_event_id']]
        source['role']='user_statement'
        argument='/[USER]/project/'+('nested/'*35)+'component.ts'
        source['text']='<command-message>migrate:start</command-message>\n<command-name>/migrate:start</command-name>\n<command-args>'+argument+'</command-args>'
        original=copy.deepcopy(data)
        output=render_report(data)
        row=re.search(r'<tr id="'+turn['id']+r'".*?</tr>',output,re.S).group(0)
        self.assertIn('component.ts',row)
        self.assertEqual(row.count('/migrate:start'),1)
        self.assertNotIn('command-message',row)
        self.assertIn(data['incidents'][0]['incident']['title'],row)
        self.assertNotIn('>Finding 1<',row)
        self.assertIn('<th>Findings</th>',output)
        self.assertIn(argument,output)
        self.assertIn('data-copy-field="request-'+source['id']+'-arguments"',output)
        payload=json.loads(re.search(r'id="report-data">(.*?)</script>',output,re.S).group(1))
        self.assertEqual(payload,original)
        self.assertEqual(data,original)

    def test_command_extraction_fails_closed_and_keeps_different_message(self):
        raw='<command-message>Preserve the API & its callers.</command-message>\n<command-name>/migrate:start</command-name>\n<command-args>--scope "two files"\n--check-only</command-args>'
        source={'role':'user_statement','text':raw}
        parsed=command_request(source)
        self.assertEqual(parsed['arguments'],'--scope "two files"\n--check-only')
        self.assertIsNone(parsed['filename'])
        self.assertIn('Preserve the API &amp; its callers.',request_preview(source,parsed))
        for text in ('Example:\n'+raw,'```\n'+raw+'\n```',raw+' extra text',raw.replace('</command-name>',''),raw+'<command-name>/other</command-name>',raw.replace('/migrate:start','not a command')):
            with self.subTest(text=text):self.assertIsNone(command_request({'role':'user_statement','text':text}))
        self.assertIsNone(command_request({'role':'assistant_statement','text':raw}))
        self.assertIsNone(command_request({'role':'user_statement'}))

    def test_command_empty_argument_is_distinct_from_absent_and_copy_keeps_whitespace(self):
        raw='<command-message>run</command-message><command-name>/run</command-name>'
        self.assertIsNone(command_request({'role':'user_statement','text':raw})['arguments'])
        parsed=command_request({'role':'user_statement','text':raw+'<command-args></command-args>'})
        self.assertEqual(parsed['arguments'],'')
        self.assertIn('(empty)',request_preview({},parsed))
        parsed=command_request({'role':'user_statement','text':raw+'<command-args>  /path/file.py\n</command-args>'})
        self.assertEqual(parsed['arguments'],'  /path/file.py\n')

    def test_source_explanation_is_saved_verbatim_and_scoped_to_its_claim(self):
        from ally_analyzer.session_investigation import save_incident
        evidence=fixture.DiagnosticTests.read(self,self.ids['event-2'])
        incident=fixture.DiagnosticTests.incident(self)
        explanation='The requested negative test failed here; this result alone does not show the later repair.'
        incident['claims'][0]['references'][0]['explanation']=explanation
        saved=save_incident(self.store,self.iid,incident)
        data=report_data(self.store,self.iid,True,True)
        original=copy.deepcopy(data)
        output=render_report(data)
        self.assertIn('id="source-relevance"',output)
        self.assertIn('data-source-context=',output)
        import html
        contexts=[json.loads(html.unescape(v)) for v in re.findall(r'data-source-context="([^"]*)"',output)]
        self.assertTrue(any(c['owner_id']==saved['id'] and c['text']==incident['claims'][0]['text'] for c in contexts))
        payload=json.loads(re.search(r'id="report-data">(.*?)</script>',output,re.S).group(1))
        self.assertEqual(payload,original)
        self.assertEqual(payload['incidents'][0]['incident']['claims'][0]['references'][0]['explanation'],explanation)
        self.assertIn('>'+explanation+'</button>',output)

    def test_complete_chronology_is_available_without_position_based_hiding(self):
        data=report_data(self.store,self.iid,True,True)
        accounting=data.get('main_accounting',data['accounting'])
        prototype=accounting['turns'][0]
        accounting['turns']=[{**copy.deepcopy(prototype),'id':'synthetic-turn-'+str(i)} for i in range(12)]
        output=render_report(data)
        rows=re.findall(r'<tr id="synthetic-turn-\d+" class="turn-row"[^>]*>',output)
        self.assertEqual(len(rows),12)
        self.assertTrue(all('hidden' not in row for row in rows))
        self.assertNotIn('data-middle-turn',output.split('<script type="application/json"')[0])
        self.assertIn('12 turns · complete chronology',output)

    def test_source_explanation_requires_inspected_reference_and_one_paragraph(self):
        from ally_analyzer.session_investigation import save_incident
        from ally_analyzer.util import AnalyzerError
        incident=fixture.DiagnosticTests.incident(self)
        ref=incident['claims'][0]['references'][0]
        ref['explanation']='This result captures the deliberately failing check.'
        with self.assertRaisesRegex(AnalyzerError,'inspected'):
            save_incident(self.store,self.iid,incident)
        fixture.DiagnosticTests.read(self,self.ids['event-2'])
        ref['explanation']='First line.\nSecond line.'
        with self.assertRaisesRegex(AnalyzerError,'line breaks'):
            save_incident(self.store,self.iid,incident)


if __name__=='__main__':unittest.main()
