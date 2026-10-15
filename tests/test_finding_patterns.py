"""Labelled synthetic pattern/relationship contracts, not model-quality evaluation."""
import copy
import unittest
from ally_analyzer.session_investigation import save_incident
from ally_analyzer.session_episodes import measure_recovery_episodes
from ally_analyzer.session_report import report_data, render_report
from ally_analyzer.session_reading import remaining_items
from ally_analyzer.util import AnalyzerError
from tests import test_session_evidence as fixture


class FindingPatternTests(unittest.TestCase):
    contract_version='single-session-v2'
    setUp=fixture.EvidenceTests.setUp
    load=fixture.EvidenceTests.load
    read=fixture.EvidenceTests.read
    read_all=fixture.EvidenceTests.read_all
    refs=fixture.EvidenceTests.refs
    incident=fixture.EvidenceTests.incident
    episode=fixture.EvidenceTests.episode
    verification=fixture.EvidenceTests.verification

    def pattern(self):
        item=self.episode();ep=item.pop('episode');narrow=copy.deepcopy(ep)
        narrow['verification'][0].update(scope_relation='narrower',basis='Synthetic second goal requires cases beyond this shared check.')
        item.update(title='Synthetic overlapping-identity pattern',resolution='unknown',pattern={
            'characteristic':'Two declared synthetic goals share captured attempts; this tests deduplication, not causal grouping.',
            'references':self.refs('event-6'),'membership_basis':'Explicit synthetic overlap fixture.',
            'episodes':[{'key':'full','title':'Synthetic fully checked goal','resolution':'recovered','episode':ep,'open_questions':[]},
                        {'key':'extra','title':'Synthetic additional cases unverified','resolution':'unknown','episode':narrow,
                         'open_questions':['No result for the additional synthetic cases.']}]})
        return item

    def test_pattern_is_one_finding_and_union_counts_overlap_once(self):
        self.read_all();saved=save_incident(self.store,self.iid,self.pattern())
        measured=measure_recovery_episodes(self.store,self.iid,[saved['id']])
        self.assertEqual(measured['episode_count'],2)
        self.assertEqual(measured['attempt_count'],6)
        self.assertEqual(measured['metrics']['tool_invocations']['value'],3)
        self.assertEqual(measured['metrics']['prompt_tokens']['value'],180)
        data=report_data(self.store,self.iid,True,True);original=copy.deepcopy(data)
        self.assertEqual(len(data['incidents']),1)
        remaining=remaining_items(data)
        self.assertEqual([e['episode_key'] for e in remaining],['extra'])
        self.assertEqual(remaining[0]['title'],'Synthetic additional cases unverified')
        output=render_report(data)
        self.assertIn('Findings · 1',output)
        self.assertIn('data-pattern-episode="extra" open',output)
        self.assertIn('data-pattern-episode="full"><summary>',output)
        self.assertIn('data-finding-episode="extra"',output)
        self.assertEqual(data,original)

    def test_pattern_cannot_hide_unknown_episode_under_recovered(self):
        self.read_all();item=self.pattern();item['resolution']='recovered'
        with self.assertRaisesRegex(AnalyzerError,'unknown episodes'):save_incident(self.store,self.iid,item)

    def test_nested_episode_cannot_treat_narrowed_pass_as_recovery(self):
        self.read_all();item=self.pattern();item['pattern']['episodes'][1]['resolution']='recovered'
        with self.assertRaisesRegex(AnalyzerError,'narrower'):save_incident(self.store,self.iid,item)

    def test_pattern_episode_keys_and_single_episode_are_unambiguous(self):
        self.read_all();item=self.pattern();item['pattern']['episodes'][1]['key']='full'
        with self.assertRaisesRegex(AnalyzerError,'keys must be distinct'):save_incident(self.store,self.iid,item)
        item=self.pattern();item['episode']=self.episode()['episode']
        with self.assertRaisesRegex(AnalyzerError,'not both'):save_incident(self.store,self.iid,item)

    def test_explicit_relationship_requires_read_membership(self):
        item=self.incident(evidence_links=[{'role':'failure','references':self.refs('event-2'),'basis':'The synthetic result records the requested negative check.'}])
        with self.assertRaisesRegex(AnalyzerError,'Read each cited'):save_incident(self.store,self.iid,item)
        self.read_all();saved=save_incident(self.store,self.iid,item)
        self.assertEqual(saved['incident']['evidence_links'],item['evidence_links'])
        item['evidence_links'][0]['references']=self.refs('event-9')
        with self.assertRaisesRegex(AnalyzerError,'explicit finding members'):save_incident(self.store,self.iid,item)

    def test_nested_goal_is_an_explicit_citation_for_relationships(self):
        self.read_all();item=self.pattern();item['task_references']=[]
        item['evidence_links']=[{'role':'request','references':self.refs('event-0'),'basis':'The nested goals cite this exact synthetic request.'}]
        saved=save_incident(self.store,self.iid,item)
        self.assertEqual(saved['incident']['evidence_links'],item['evidence_links'])


if __name__=='__main__':unittest.main()
