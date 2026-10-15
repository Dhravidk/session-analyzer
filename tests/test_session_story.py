"""Synthetic reader-guide contracts; these checks do not certify model prose."""
import copy
import unittest

from ally_analyzer.session_investigation import save_incident, records
from ally_analyzer.session_review import update_workflow
from ally_analyzer.util import AnalyzerError
from tests import test_session_evidence as fixture


class SessionStoryTests(unittest.TestCase):
    contract_version='single-session-v2'
    setUp=fixture.EvidenceTests.setUp
    load=fixture.EvidenceTests.load
    read=fixture.EvidenceTests.read
    read_all=fixture.EvidenceTests.read_all
    refs=fixture.EvidenceTests.refs
    incident=fixture.EvidenceTests.incident
    episode=fixture.EvidenceTests.episode
    verification=fixture.EvidenceTests.verification

    def guided(self):
        item=self.episode()
        def event(key,title,name):
            ref={**self.refs(name)[0],'explanation':title}
            return {'key':key,'title':title,'explanation':title+' This is a labelled synthetic fixture.',
                    'anchor_source_id':ref['source_id'],'primary_source_id':ref['source_id'],
                    'references':[ref],'limitations':[]}
        item['reader_guide']={'name':'Synthetic fixture repair','takeaway':'The repaired fixture passed its check.',
            'references':self.refs('event-6'),'limitations':[],
            'events':[event('failed','The fixture check failed.','event-2'),event('passed','The repaired fixture check passed.','event-6')]}
        return item

    def test_managed_requirement_is_explicit_and_does_not_mutate_submission(self):
        self.read_all();update_workflow(self.store,self.iid,'investigate',reader_guides=True)
        with self.assertRaisesRegex(AnalyzerError,'Save reader_guide'):
            save_incident(self.store,self.iid,self.episode())
        self.assertEqual(records(self.store,self.iid,'claim'),[])
        item=self.guided();before=copy.deepcopy(item)
        saved=save_incident(self.store,self.iid,item)
        self.assertEqual(saved['incident'],before);self.assertEqual(item,before)

    def test_legacy_contract_still_accepts_an_unguided_incident(self):
        self.read_all();saved=save_incident(self.store,self.iid,self.episode())
        self.assertNotIn('reader_guide',saved['incident'])

    def test_unread_and_unrelated_sources_cannot_be_hidden_in_a_guide(self):
        with self.assertRaisesRegex(AnalyzerError,'Read each cited'):
            save_incident(self.store,self.iid,self.guided())
        self.read_all();item=self.guided()
        item['reader_guide']['references']=self.refs('event-9')
        with self.assertRaisesRegex(AnalyzerError,'explicit incident'):
            save_incident(self.store,self.iid,item)
        self.assertEqual(records(self.store,self.iid,'incident'),[])

    def test_decisive_source_anchor_keys_and_order_are_validated(self):
        self.read_all()
        for mutation,message in [
            (lambda g:g['events'][0].update(primary_source_id=self.ids['event-6']),'both be cited'),
            (lambda g:g['events'][1].update(key='failed'),'distinct'),
            (lambda g:g['events'].reverse(),'anchor order'),
            (lambda g:g['events'][0].update(episode_key='invented'),'requires a saved pattern'),
        ]:
            item=self.guided();mutation(item['reader_guide'])
            with self.subTest(message=message),self.assertRaisesRegex(AnalyzerError,message):
                save_incident(self.store,self.iid,item)

    def test_pattern_events_bind_to_existing_episode_and_its_sources(self):
        self.read_all();item=self.guided();ep=item.pop('episode')
        item['pattern']={'characteristic':'Synthetic shared fixture checks.','references':self.refs('event-2'),
            'membership_basis':'Labelled overlap test, not a causal claim.',
            'episodes':[{'key':key,'title':'Synthetic '+key,'resolution':'recovered','episode':copy.deepcopy(ep),'open_questions':[]}
                        for key in ('one','two')]}
        with self.assertRaisesRegex(AnalyzerError,'saved episode_key'):save_incident(self.store,self.iid,item)
        for event,key in zip(item['reader_guide']['events'],('one','two')):event['episode_key']=key
        save_incident(self.store,self.iid,item)
        incomplete=copy.deepcopy(item);incomplete['reader_guide']['events'].pop()
        with self.assertRaisesRegex(AnalyzerError,'Each saved pattern episode'):
            save_incident(self.store,self.iid,incomplete)
        item['member_event_ids'].append(self.ids['event-9'])
        item['reader_guide']['events'][-1]['references']+=self.refs('event-9')
        item['reader_guide']['events'][-1].update(primary_source_id=self.ids['event-9'],anchor_source_id=self.ids['event-9'])
        with self.assertRaisesRegex(AnalyzerError,'selected episode'):save_incident(self.store,self.iid,item)

    def test_main_source_cannot_be_anchored_in_an_unrelated_turn(self):
        self.read_all();item=self.guided();event=item['reader_guide']['events'][0]
        item['member_event_ids'].append(self.ids['event-9'])
        event['references']+=self.refs('event-9');event['anchor_source_id']=self.ids['event-9']
        with self.assertRaisesRegex(AnalyzerError,'same turn'):save_incident(self.store,self.iid,item)


if __name__=='__main__':unittest.main()
