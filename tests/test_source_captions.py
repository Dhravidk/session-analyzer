"""Synthetic source labels identify saved records without generating judgments."""
import copy
import html
import json
import re
import unittest

from ally_analyzer.session_report import source_caption, reference_list


class SourceCaptionTests(unittest.TestCase):
    def fixture(self):
        data={'sources':{
            'input':{'role':'tool_call','tool_ids':['call'], 'text':'Tool Bash\nInput: '+json.dumps({'command':'pytest tests/test_csv.py', 'description':'Check CSV escaping'}), 'timestamp':'2026-10-15T10:20:30Z'},
            'result':{'role':'tool_result','tool_ids':['call'],'text':'FAIL: field was not escaped', 'timestamp':'2026-10-15T10:20:31Z'}},
            'tools':[{'id':'call','name':'Bash','evidence_id':'input'}],
            'accounting':{'turns':[{'event_ids':['input','result']}]}}
        return data

    def test_input_and_result_retain_direction_and_use_saved_description(self):
        data=self.fixture();before=copy.deepcopy(data)
        for sid,direction in [('input','input'),('result','result')]:
            label=source_caption({'source_id':sid},data)
            self.assertEqual(label['title'],'Check CSV escaping')
            self.assertIn('Bash '+direction+' · Turn 1',label['meta'])
            self.assertNotIn('passed',label['title'])
        self.assertEqual(data,before)

    def test_saved_explanation_and_qualification_are_not_truncated_or_rewritten(self):
        data=self.fixture();explanation='Saved explanation '+('with exact detail, '*10)
        ref={'source_id':'result','explanation':explanation,'start_char':0,'end_char':4,'text_sha256':'synthetic'}
        output=reference_list([ref],{'text':'Exact saved claim'},data)
        self.assertEqual(source_caption(ref,data)['title'],explanation)
        self.assertEqual(source_caption(ref,data)['full'],explanation)
        self.assertIn('Sources · 1',output)
        encoded=re.search(r'data-ref="([^"]+)"',output).group(1)
        self.assertEqual(json.loads(html.unescape(encoded)),ref)
        self.assertNotRegex(output,r'>Source \d+<')

    def review(self, owner='claim', sentence='The saved full-suite result reports two failed suites.'):
        return {'check':{'record_id':owner,'verdict':'qualified','evidence_checks':[
            {'reference':{'source_id':'result'},'supports_or_contradicts':sentence}]},
            'verified_quote_ranges':[{'source_id':'result','text_sha256':'synthetic','start_char':0,'end_char':4}]}

    def test_current_owner_review_supplies_label_without_changing_citation(self):
        data=self.fixture();data['sources']['result']['text_sha256']='synthetic'
        data['review_checks']=[self.review()];before=copy.deepcopy(data)
        ref={'source_id':'result','text_sha256':'synthetic','start_char':0,'end_char':10}
        context={'owner_id':'claim'}
        caption=source_caption(ref,data,context)
        self.assertEqual(caption['title'],'The saved full-suite result reports two failed suites.')
        self.assertIn('Saved review · qualified',caption['meta'])
        output=reference_list([ref],context,data)
        self.assertEqual(json.loads(html.unescape(re.search(r'data-ref="([^"]+)"',output).group(1))),ref)
        self.assertEqual(data,before)
        ref['explanation']='The citation-specific sentence takes precedence.'
        self.assertEqual(source_caption(ref,data,context)['title'],ref['explanation'])

    def test_wrong_owner_changed_source_and_outside_range_never_borrow_review(self):
        data=self.fixture();data['sources']['result']['text_sha256']='synthetic';data['review_checks']=[self.review()]
        for ref,owner in [({'source_id':'result'},'different-claim'),
                          ({'source_id':'result','text_sha256':'old','start_char':0,'end_char':10},'claim'),
                          ({'source_id':'result','text_sha256':'synthetic','start_char':5,'end_char':10},'claim')]:
            with self.subTest(ref=ref,owner=owner):
                self.assertEqual(source_caption(ref,data,{'owner_id':owner})['title'],'Explanation not saved')
        data['sources']['result']['text_sha256']='changed'
        self.assertEqual(source_caption({'source_id':'result'},data,{'owner_id':'claim'})['title'],'Explanation not saved')

    def test_latest_review_replaces_prior_notes_and_failed_check_stays_visible(self):
        data=self.fixture();data['sources']['result']['text_sha256']='synthetic'
        data['review_checks']=[self.review(),self.review(sentence='This result contradicts the saved completion claim.')]
        data['review_checks'][-1]['check']['verdict']='needs_revision'
        caption=source_caption({'source_id':'result'},data,{'owner_id':'claim'})
        self.assertEqual(caption['title'],'This result contradicts the saved completion claim.')
        self.assertIn('needs revision',caption['meta'])
        data['review_checks'][-1]['verified_quote_ranges']=[]
        self.assertEqual(source_caption({'source_id':'result'},data,{'owner_id':'claim'})['title'],'Explanation not saved')
        del data['review_checks'][-1]['check']['evidence_checks']
        self.assertEqual(source_caption({'source_id':'result'},data,{'owner_id':'claim'})['title'],'Explanation not saved')

    def test_filename_is_not_presented_as_explanation_of_a_claim(self):
        data=self.fixture();data['sources']['input']['text']='Tool Bash\nInput: '+json.dumps({'file_path':'/tmp/tasks/bta8tnsqk.output'})
        self.assertEqual(source_caption({'source_id':'result'},data,{'owner_id':'claim'})['title'],'Explanation not saved')
        self.assertEqual(source_caption({'source_id':'result'},data)['title'],'tasks/bta8tnsqk.output')

    def test_paths_and_commands_use_literal_fields_without_reading_other_files(self):
        data=self.fixture();data['sources']['input']['text']='Tool Bash\nInput: '+json.dumps({'file_path':'/[USER]/project/theme-items/index.d.ts'})
        self.assertEqual(source_caption({'source_id':'result'},data)['title'],'theme-items/index.d.ts')
        data['sources']['input']['text']='Tool Bash\nInput: '+json.dumps({'command':'pytest tests/test_csv.py'})
        self.assertEqual(source_caption({'source_id':'result'},data)['title'],'pytest tests/test_csv.py')

    def test_ambiguous_tool_membership_does_not_borrow_a_description(self):
        data=self.fixture();data['tools'].append({'id':'other','name':'Read','evidence_id':'input'})
        data['sources']['result']['tool_ids'].append('other')
        self.assertEqual(source_caption({'source_id':'result'},data)['title'],'FAIL: field was not escaped')
        self.assertTrue(source_caption({'source_id':'result'},data)['meta'].startswith('Tool result'))

    def test_task_notification_uses_only_its_saved_summary(self):
        data={'sources':{'notice':{'role':'other','text':'<task-notification><task-id>x</task-id><status>killed</status><summary>Background check was stopped</summary></task-notification>'}}}
        caption=source_caption({'source_id':'notice'},data)
        self.assertEqual(caption['title'],'Background check was stopped')
        self.assertEqual(caption['meta'],'Task notification')

    def test_missing_sources_and_thinking_do_not_create_evidence_excerpts(self):
        data={'sources':{'thinking':{'role':'assistant_thinking','text':'Private planning text','agent_id':'child-A'},'missing':{'role':'assistant_statement'}}}
        self.assertEqual(source_caption({'source_id':'thinking'},data)['title'],'Thinking record')
        self.assertIn('Agent child-A',source_caption({'source_id':'thinking'},data)['meta'])
        self.assertIn('Text not included',source_caption({'source_id':'missing'},data)['meta'])
        self.assertIn('Not included in export',source_caption({'source_id':'absent'},data)['meta'])

    def test_duplicate_previews_are_distinguishable_and_labels_are_escaped(self):
        data=self.fixture();data['sources']['second-result']=copy.deepcopy(data['sources']['result'])
        data['sources']['input']['text']='Tool Bash\nInput: '+json.dumps({'description':'<script>literal</script>'})
        output=reference_list([{'source_id':'result'},{'source_id':'second-result'}],data=data)
        self.assertIn('&lt;script&gt;literal&lt;/script&gt;',output)
        self.assertNotIn('<script>literal</script>',output)
        # Give both records the same recorded turn to exercise equal captions.
        data['accounting']['turns'][0]['event_ids'].append('second-result')
        output=reference_list([{'source_id':'result'},{'source_id':'second-result'}],data=data)
        self.assertIn('UTC · result</span>',output)
        self.assertIn('UTC · d-result</span>',output)


if __name__=='__main__':unittest.main()
