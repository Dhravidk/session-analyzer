"""Explicit synthetic association fixtures; prose never classifies a link."""
import copy
import unittest
from ally_analyzer.session_finding_links import finding_links


class FindingLinkTests(unittest.TestCase):
    def fixture(self):
        incident={'title':'Synthetic lookup collection','membership_basis':'Synthetic separate lookups.',
                  'member_event_ids':['bad','good','unknown'],'tool_ids':['lookup'],
                  'task_references':[{'source_id':'request'}], 'recovery_references':[{'source_id':'good'}],
                  'counterevidence':[], 'claims':[{'text':'This prose mentions failure and recovery but must not classify unknown.',
                                                'references':[{'source_id':'unknown'}]}]}
        data={'accounting':{'turns':[{'id':'t1','event_ids':['request','bad','unknown'],'tool_ids':['lookup']},
                                   {'id':'t2','event_ids':['intervening'],'tool_ids':[]},
                                   {'id':'t3','event_ids':['good'],'tool_ids':[]}]},
              'sources':{sid:{'id':sid,'role':'tool_result','text':'Synthetic '+sid} for sid in ['bad','good','unknown','intervening']},
              'tools':[{'id':'lookup','evidence':['bad'],'outcome':'execution_failure'}]}
        return data,{'id':'finding','incident':incident}

    def test_failure_recovery_and_unknown_have_different_explicit_roles(self):
        data,saved=self.fixture();original=copy.deepcopy((data,saved))
        links=finding_links(data,saved)
        self.assertEqual(set(links),{'t1','t3'})
        self.assertEqual(links['t3']['label'],'Recovery evidence')
        self.assertEqual(links['t3']['evidence'][0]['ref']['source_id'],'good')
        entries={e['ref']['source_id']:e for e in links['t1']['evidence']}
        self.assertEqual(entries['unknown']['label'],'Related evidence')
        self.assertEqual(entries['bad']['label'],'Failure evidence')
        self.assertEqual(entries['request']['label'],'Request context')
        self.assertEqual((data,saved),original)

    def test_multiple_roles_are_preserved_without_claiming_success(self):
        data,saved=self.fixture();saved['incident']['recovery_references'].append({'source_id':'bad'})
        entry=next(e for e in finding_links(data,saved)['t1']['evidence'] if e['ref']['source_id']=='bad')
        self.assertEqual(entry['label'],'Failure and recovery')
        self.assertIn('Recorded tool outcome: execution_failure',entry['bases'])
        self.assertIn('Saved recovery references',entry['bases'])

    def test_unrelated_failure_in_a_linked_turn_is_not_added(self):
        data,saved=self.fixture();data['accounting']['turns'][0]['event_ids'].append('other-failure')
        data['sources']['other-failure']={'id':'other-failure','role':'tool_result'}
        data['tools'].append({'id':'other','evidence':['other-failure'],'outcome':'execution_failure'})
        self.assertNotIn('other-failure',{e['ref']['source_id'] for e in finding_links(data,saved)['t1']['evidence']})

    def test_correct_denial_is_not_promoted_to_execution_failure(self):
        data,saved=self.fixture();data['tools'][0]['outcome']='permission_denied'
        entry=next(e for e in finding_links(data,saved)['t1']['evidence'] if e['ref']['source_id']=='bad')
        self.assertEqual(entry['label'],'Related evidence')

    def test_explicit_saved_relationship_retains_exact_explanation(self):
        data,saved=self.fixture()
        saved['incident']['evidence_links']=[{'role':'verification','references':[{'source_id':'unknown','explanation':'The synthetic check covers the original scope.'}],'basis':'Synthetic explicit association.'}]
        entry=next(e for e in finding_links(data,saved)['t1']['evidence'] if e['ref']['source_id']=='unknown')
        self.assertEqual(entry['label'],'Verification evidence')
        self.assertEqual(entry['ref']['explanation'],'The synthetic check covers the original scope.')

    def test_cited_result_precedes_request_context_without_inventing_a_role(self):
        data,saved=self.fixture();data['tools'][0]['outcome']='completed'
        saved['incident']['counterevidence']=[{'source_id':'bad'}]
        saved['incident']['claims'][0]['references'].append({'source_id':'bad'})
        entry=finding_links(data,saved)['t1']['evidence'][0]
        self.assertEqual(entry['ref']['source_id'],'unknown')
        self.assertEqual(entry['label'],'Related evidence')


if __name__=='__main__':unittest.main()
