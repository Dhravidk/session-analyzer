"""Developer reading aids must preserve saved judgments and evidence scope."""
import copy
import json
import re
import unittest
from ally_analyzer.session_investigation import save_incident
from ally_analyzer.session_requirements import save_requirement_map
from ally_analyzer.session_reading import remaining_items, remaining_work_text, requirement_anchor, related_turns
from ally_analyzer.session_report import render_report, report_data
from tests import test_session_evidence as fixture


class SessionReadingTests(unittest.TestCase):
    contract_version='single-session-v2'
    setUp=fixture.EvidenceTests.setUp
    load=fixture.EvidenceTests.load
    read=fixture.EvidenceTests.read
    read_all=fixture.EvidenceTests.read_all
    refs=fixture.EvidenceTests.refs
    requirement=fixture.EvidenceTests.requirement
    verification=fixture.EvidenceTests.verification
    mapped=fixture.EvidenceTests.mapped
    incident=fixture.EvidenceTests.incident
    attribution=fixture.EvidenceTests.attribution
    episode=fixture.EvidenceTests.episode

    def test_unverified_is_not_failed_and_handoff_does_not_invent_action(self):
        self.read_all()
        item=self.requirement(status='unverified',status_basis='The check predates the final edit.',
                              missing_evidence=['No check against the final revision.'])
        saved=save_requirement_map(self.store,self.iid,self.mapped([item]))
        data=report_data(self.store,self.iid,True,True);before=copy.deepcopy(data)
        remaining=remaining_items(data)
        self.assertEqual(remaining[0]['status'],'Unverified')
        self.assertNotIn('next_action',remaining[0])
        text=remaining_work_text(data)
        self.assertIn(item['scope'],text)
        self.assertIn(item['missing_evidence'][0],text)
        self.assertIn(self.ids['event-6'],text)
        self.assertNotIn('Saved next action:',text)
        html=render_report(data)
        self.assertLess(html.index('id="remaining-heading"'),html.index('id="requirements"'))
        anchor=requirement_anchor(saved['id'],item['key'])
        self.assertIn('data-open-requirement="'+anchor+'"',html)
        self.assertIn('id="detail-'+anchor+'" class="requirement-detail" hidden',html)
        self.assertEqual(json.loads(re.search(r'id="report-data">(.*?)</script>',html,re.S).group(1)),before)
        self.assertEqual(data,before)

    def test_completed_recovered_and_expected_no_action_do_not_create_handoff(self):
        self.read_all();save_requirement_map(self.store,self.iid,self.mapped())
        save_incident(self.store,self.iid,self.incident(resolution='recovered',remaining_action='none'))
        data=report_data(self.store,self.iid,True,True)
        self.assertEqual(remaining_items(data),[])
        self.assertEqual(remaining_work_text(data),'')
        self.assertNotIn('Copy remaining work</button>',render_report(data))

    def test_saved_next_action_and_review_dissent_survive_copy(self):
        self.read_all()
        saved=save_incident(self.store,self.iid,self.incident(resolution='unknown',attribution=self.attribution()))
        data=report_data(self.store,self.iid,True,True)
        data['review_checks']=[{'check':{'record_id':saved['id'],'verdict':'qualified',
            'assessment':'The retained evidence does not settle instruction order.',
            'remaining_uncertainty':['Both readings remain possible.']}}]
        text=remaining_work_text(data)
        self.assertIn('Outcome unknown:',text)
        self.assertIn('Saved next action: '+self.attribution()['immediate_next_action'],text)
        self.assertIn('Both readings remain possible.',text)
        self.assertIn('Claude review qualified; see saved assessment',render_report(data))

    def test_turn_focus_uses_explicit_identity_not_adjacent_or_similar_work(self):
        data={'accounting':{'turns':[
            {'id':'first','event_ids':['request-a','result-a'],'tool_ids':['tool-a']},
            {'id':'intervening','event_ids':['request-b'],'tool_ids':['tool-b']},
            {'id':'last','event_ids':['request-c','result-c'],'tool_ids':['tool-c']}]}}
        self.assertEqual(related_turns(data,[{'source_id':'result-c'}],tool_ids=['tool-a']),['first','last'])
        self.assertEqual(related_turns(data,event_ids=['unknown-child']),[])

    def test_not_met_is_distinct_from_unverified_and_keeps_full_basis(self):
        self.read_all()
        item=self.requirement(status='contradicted',status_basis='The explicit prerequisite was skipped.')
        save_requirement_map(self.store,self.iid,self.mapped([item]))
        data=report_data(self.store,self.iid,True,True)
        self.assertEqual(remaining_items(data)[0]['status'],'Not met')
        self.assertIn(item['status_basis'],render_report(data))
        self.assertIn('Requirement inventory: partial',remaining_work_text(data))


if __name__=='__main__':unittest.main()
