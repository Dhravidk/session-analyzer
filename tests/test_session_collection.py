"""Multi-log behavior on labelled synthetic sessions; no Claude/model invocation."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ally_analyzer.engine import analyze_dataset
from ally_analyzer.ingest import import_bundle
from ally_analyzer.service import Service
from ally_analyzer.session_collection import start_session_collection
from ally_analyzer.session_investigation import records
from ally_analyzer.session_scope import get_run, scope_rows, start_session_investigation
from ally_analyzer.store import Store
from ally_analyzer.util import AnalyzerError, canonical
from tests.helpers import response, write_log
from tests.test_session_workflow import human
from tests.test_session_agents import linked_fixture


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.store = Store(self.root/'store')
        self.paths = []
        for index, sid in enumerate(('synthetic-a', 'synthetic-b', 'synthetic-outside')):
            first = 10 * index
            request = human(first, 'Synthetic request: draft a plan; get approval before implementation.', session=sid)
            ending = response(first+1, session=sid, content=[{'type':'text', 'text':'Synthetic ending: draft saved; implementation awaits approval.'}])
            ending['message']['model'] = 'claude-opus-5-5'
            self.paths.append(write_log(self.root/sid/'session.jsonl', [request, ending]))
        self.aid = analyze_dataset(self.store, import_bundle(self.store, self.paths)['dataset_id'])['analysis_id']
        self.service = Service(self.store, allow_content=True); self.addCleanup(self.service.close)
        self.selected = self.service.call('start_session_collection', {'analysis_id':self.aid,
                          'session_ids':['synthetic-a','synthetic-b'], 'purpose':'Synthetic separate review'})
        self.cid = self.selected['collection_id']; self.members = self.selected['members']

    def call(self, name, **args):
        return self.service.call(name, {'collection_id':self.cid, **args})

    def read_all(self):
        checks = []
        for member in self.members:
            iid = member['investigation_id']
            for row in scope_rows(self.store, get_run(self.store, iid)):
                read = self.service.call('read_investigation_evidence', {'investigation_id':iid, 'source_id':row['id']})
                if row['kind'] == 'user':
                    checks.extend({'investigation_id':iid, 'aspect':aspect, 'source_id':row['id'],
                           'access_id':read['request_id'], 'quote':read['text'][:65],
                           'basis':'Synthetic request establishes the approval boundary; completion needs result evidence.'}
                           for aspect in ('task_outcome','instruction_following'))
        return checks

    def prose(self, individual=False):
        entries = []; bodies = []
        for m in self.members:
            sid = m['session_id']
            outcome = sid + ': Task outcome: the assistant says the draft was saved; delivery is unverified.'
            compliance = sid + ': Instruction following: the captured ending preserves approval before implementation.'
            text = outcome + '\n' + compliance
            item = {'investigation_id':m['investigation_id'], 'compliance':{'task_outcome':outcome, 'instruction_following':compliance}}
            if individual: item['body'] = text
            entries.append(item); bodies.append(text)
        return entries, 'Retain the evidenced approval boundary; verify saved drafts before proposing a skill edit.\n\n' + '\n\n'.join(bodies)

    def draft(self):
        self.read_all(); entries, body = self.prose()
        return self.call('prepare_collection_reply', sessions=entries, body=body)

    def test_scope_is_explicit_and_cannot_open_other_sessions_or_legacy_tools(self):
        self.assertEqual(len(self.members), 2)
        self.assertIsNone(self.service.investigation_id)
        outside = start_session_investigation(self.store, self.aid, 'synthetic-outside', 'Synthetic unrelated root')['investigation']['id']
        with self.assertRaisesRegex(AnalyzerError, 'outside'):
            self.service.call('get_session_overview', {'investigation_id':outside})
        for name,args in [('list_sessions',{'analysis_id':self.aid}), ('get_metrics',{'analysis_id':self.aid}),
                          ('start_session_investigation',{'analysis_id':self.aid,'session_id':'synthetic-outside','purpose':'Bypass'})]:
            with self.subTest(name=name), self.assertRaises(AnalyzerError): self.service.call(name,args)
        self.read_all()  # Switching between exactly the selected members works.

    def test_duplicate_selection_resumes_same_collection_and_roots(self):
        again = start_session_collection(self.store, self.aid, ['synthetic-a','synthetic-b'], 'Synthetic separate review')
        self.assertEqual(again['collection_id'], self.cid)
        self.assertEqual([m['investigation_id'] for m in again['members']], [m['investigation_id'] for m in self.members])
        other = start_session_collection(self.store, self.aid, ['synthetic-a'], 'Another explicit selection')
        with self.assertRaises(AnalyzerError): self.call('get_session_collection', collection_id=other['collection_id'])

    def test_whole_readout_requires_every_selected_request(self):
        entries, body = self.prose()
        blocked = self.call('prepare_collection_reply', sessions=entries, body=body)
        self.assertEqual(blocked['status'], 'needs_revision')
        self.assertEqual(len(blocked['issues']), 2)
        self.assertTrue(all(i['code']=='unread_task_requests' for i in blocked['issues']))
        self.read_all()
        with self.assertRaises(AnalyzerError): self.call('prepare_collection_reply', sessions=entries[:1], body=body)
        with self.assertRaises(AnalyzerError): self.call('prepare_collection_reply', sessions=[entries[0],entries[0]], body=body)
        entries[0]['compliance']['task_outcome'] = 'Absent exact span'
        missing = self.call('prepare_collection_reply', sessions=entries, body=body)
        self.assertIn('missing_task_outcome_assessment',{i['code'] for i in missing['issues']})

    def test_combined_review_is_automatic_gate_and_accepted_text_is_immutable(self):
        draft = self.draft(); did = draft['draft_id']
        self.assertEqual(draft['status'], 'review_required'); self.assertNotIn('reply', draft)
        before = copy.deepcopy(records(self.store, self.cid, 'collection_reply_draft'))
        self.assertEqual(self.draft()['draft_id'], did)
        fetched = self.call('get_collection_reply_draft', draft_id=did)
        # draft() reread every root on replay; reads stay fresh for the same draft.
        self.assertTrue(all(c['unread_request_count']==0 for c in fetched['review_request_coverage'].values()))
        checks = self.read_all(); entries,body = self.prose()
        body = 'Supported synthetic recommendation, checked against both roots.\n\n' + body
        ready = self.call('submit_collection_reply_review', draft_id=did, sessions=entries, body=body,
                          notes='Synthetic review; do not turn reported draft creation into verified delivery.', source_checks=checks)
        self.assertEqual(ready['status'],'ready',ready)
        self.assertTrue(ready['reply'].startswith('Estimated cost across 2 selected sessions:'))
        self.assertTrue(ready['reply'].endswith(body))
        self.assertEqual(records(self.store, self.cid, 'collection_reply_draft'),before)
        self.assertEqual(self.call('get_reviewed_collection_reply',draft_id=did)['reply'],ready['reply'])
        replay = self.call('submit_collection_reply_review',draft_id=did,sessions=entries,body=body,
                          notes='Synthetic review; do not turn reported draft creation into verified delivery.',source_checks=checks)
        self.assertEqual(replay['review_id'],ready['review_id'])
        with self.assertRaisesRegex(AnalyzerError,'immutable accepted'):
            self.call('submit_collection_reply_review',draft_id=did,sessions=entries,body=body+'Changed.',notes='New',source_checks=checks)

    def test_new_combined_and_individual_drafts_wait_for_fresh_sources_without_changing_storage(self):
        for mode in ('combined', 'individual'):
            with self.subTest(mode=mode):
                service=Service(self.store,allow_content=True);self.addCleanup(service.close)
                selected=service.call('start_session_collection',{'analysis_id':self.aid,
                    'session_ids':['synthetic-a','synthetic-b'],'purpose':'Synthetic source-first '+mode,'output_mode':mode})
                cid=selected['collection_id']
                entries=[];texts=[]
                for member in selected['members']:
                    iid=member['investigation_id']
                    for row in scope_rows(self.store,get_run(self.store,iid)):
                        service.call('read_investigation_evidence',{'investigation_id':iid,'source_id':row['id']})
                    outcome=iid+' task unverified.';following=iid+' approval preserved.'
                    entry={'investigation_id':iid,'compliance':{'task_outcome':outcome,'instruction_following':following}}
                    text=outcome+' '+following
                    if mode=='individual':entry['body']=text
                    entries.append(entry);texts.append(text)
                args={'collection_id':cid,'sessions':entries}
                if mode=='combined':args['body']=' '.join(texts)
                did=service.call('prepare_collection_reply',args)['draft_id']
                original=records(self.store,cid,'collection_reply_draft')
                def fetch():return service.call('get_collection_reply_draft',{'collection_id':cid,'draft_id':did})
                hidden=fetch()
                self.assertTrue(hidden['draft_content_withheld'])
                self.assertNotIn('body',hidden['draft'])
                self.assertTrue(all('body' not in s and 'compliance' not in s for s in hidden['draft']['sessions']))
                # Reading only one root cannot release either form of the handoff.
                for index,member in enumerate(selected['members']):
                    iid=member['investigation_id']
                    for row in scope_rows(self.store,get_run(self.store,iid)):
                        service.call('read_investigation_evidence',{'investigation_id':iid,'source_id':row['id']})
                    self.assertEqual(fetch()['draft_content_withheld'],index==0)
                self.assertEqual(fetch()['draft'],original[0])
                self.assertEqual(records(self.store,cid,'collection_reply_draft'),original)

    def test_review_requires_fresh_reads_in_both_sessions_and_rejects_cross_scope_quotes(self):
        checks = self.read_all(); entries,body = self.prose()
        did = self.call('prepare_collection_reply',sessions=entries,body=body)['draft_id']
        denied = self.call('submit_collection_reply_review',draft_id=did,sessions=entries,body=body,notes='Synthetic stale reads',source_checks=checks)
        self.assertEqual(denied['status'],'needs_revision')
        self.assertIn('review_requests_not_reread',{i['code'] for i in denied['issues']})
        checks = self.read_all(); checks[0]['investigation_id'] = self.members[1]['investigation_id']
        denied = self.call('submit_collection_reply_review',draft_id=did,sessions=entries,body=body,notes='Synthetic wrong-session quote',source_checks=checks)
        self.assertIn('invalid_review_source',{i['code'] for i in denied['issues']})
        history=self.call('get_collection_reply_draft',draft_id=did,include_reviews=True)['review_history']
        self.assertEqual(len(history),2)
        self.assertEqual(history[1]['submission']['notes'],'Synthetic wrong-session quote')
        self.assertEqual(self.call('get_reviewed_collection_reply',draft_id=did)['status'],'review_incomplete')
        self.assertNotIn('reply',denied)
        with self.assertRaisesRegex(AnalyzerError,'Two review submissions'):
            self.call('submit_collection_reply_review',draft_id=did,sessions=entries,body=body,notes='Third attempt',source_checks=[])

    def test_individual_readouts_preserve_authored_bodies_and_cost_for_each(self):
        own = Service(self.store,allow_content=True); self.addCleanup(own.close)
        self.service = own
        self.selected = own.call('start_session_collection',{'analysis_id':self.aid,'session_ids':['synthetic-a','synthetic-b'],
                                  'purpose':'Synthetic individual readouts','output_mode':'individual'})
        self.cid = self.selected['collection_id']; self.members = self.selected['members']
        self.read_all(); entries,_ = self.prose(individual=True)
        did = self.call('prepare_collection_reply',sessions=entries)['draft_id']; checks = self.read_all()
        ready = self.call('submit_collection_reply_review',draft_id=did,sessions=entries,notes='Synthetic individual review',source_checks=checks)
        self.assertEqual(ready['status'],'ready',ready)
        for entry in entries: self.assertIn(entry['body'],ready['reply'])
        self.assertEqual(ready['reply'].count('Estimated session cost:'),2)
        self.assertIn('Estimated cost across 2 selected sessions:',ready['reply'])

    def test_metadata_policy_and_unrequested_resource_detail_are_preserved(self):
        self.service.allow_content=False; entries,body=self.prose()
        blocked=self.call('prepare_collection_reply',sessions=entries,body='Use prompt caching and automatic session compaction.\n'+body)
        self.assertIn('unrequested_cache_detail',{i['code'] for i in blocked['issues']})
        self.assertIn('unrequested_compaction_detail',{i['code'] for i in blocked['issues']})
        did=self.call('prepare_collection_reply',sessions=entries,body=body)['draft_id']
        ready=self.call('submit_collection_reply_review',draft_id=did,sessions=entries,body=body,notes='Synthetic metadata only; outcomes unverified.',source_checks=[])
        self.assertEqual(ready['status'],'ready')
        # Metadata checks cannot certify these judgments; prose is never generated by the renderer.
        self.assertIn('unverified',ready['reply'])

    def test_content_policy_cannot_be_lowered_to_fetch_a_disclosed_draft(self):
        did=self.draft()['draft_id']; self.service.allow_content=False
        for tool in ('get_collection_reply_draft','get_reviewed_collection_reply'):
            with self.subTest(tool=tool), self.assertRaises(AnalyzerError): self.call(tool,draft_id=did)

    def test_one_session_binding_cannot_be_widened_into_collection(self):
        single=Service(self.store); self.addCleanup(single.close)
        single.call('get_session_overview',{'investigation_id':self.members[0]['investigation_id']})
        for tool,args in [('get_session_collection',{'collection_id':self.cid}),
                          ('start_session_collection',{'analysis_id':self.aid,'session_ids':['synthetic-a'],'purpose':'Widen'})]:
            with self.subTest(tool=tool), self.assertRaises(AnalyzerError): single.call(tool,args)

    def test_explicit_collection_can_be_resumed_from_environment(self):
        with patch.dict(os.environ,{'ALLY_ANALYZER_COLLECTION_ID':self.cid}):
            resumed=Service(self.store); self.addCleanup(resumed.close)
        self.assertEqual(resumed.collection_members,self.service.collection_members)
        self.assertEqual(resumed.call('get_definitions',{})['bound_collection_id'],self.cid)

    def test_sources_and_source_cost_ignore_analyzer_usage(self):
        before=[p.read_bytes() for p in self.paths]
        opening=self.call('get_session_collection')['collection_readout']['opening']
        with self.store.connect() as db:
            for member in self.members:
                run=get_run(self.store,member['investigation_id']);run['analyzer_usage']={'cost_usd':'9999','input_tokens':99999999}
                db.execute('UPDATE session_runs SET payload=? WHERE id=?',(canonical(run),run['id']))
        self.assertEqual(self.call('get_session_collection')['collection_readout']['opening'],opening)
        self.assertEqual([p.read_bytes() for p in self.paths],before)

    def test_shared_history_and_duplicate_file_count_once_in_combined_cost(self):
        original=json.loads(self.paths[0].read_text().splitlines()[1])
        copied=copy.deepcopy(original); copied['uuid']='synthetic-copied-frame';copied['sessionId']='synthetic-b'
        with self.paths[1].open('a') as f:f.write(json.dumps(copied)+'\n')
        aid=analyze_dataset(self.store,import_bundle(self.store,[*self.paths[:2],self.paths[0]])['dataset_id'])['analysis_id']
        selected=start_session_collection(self.store,aid,['synthetic-a','synthetic-b'],'Synthetic overlapping history')
        usage=selected['collection_readout']['usage']
        self.assertEqual(selected['accounting_coverage']['unique_responses'],2)
        self.assertEqual(usage['input_tokens']['value'],120)
        self.assertEqual(usage['output_tokens']['value'],80)
        self.assertEqual(usage['input_tokens']['cost_usd'],'0.000292')
        own=[m['session_readout']['usage']['input_tokens']['value'] for m in selected['members']]
        self.assertEqual(sum(own),180)  # Inclusive totals are deliberately non-additive.

    def test_unknown_rate_or_conflicting_copy_is_not_treated_as_zero(self):
        rows=[json.loads(line) for line in self.paths[1].read_text().splitlines()]
        rows[1]['message']['model']='synthetic-unknown-model'
        write_log(self.paths[1],rows)
        aid=analyze_dataset(self.store,import_bundle(self.store,self.paths[:2])['dataset_id'])['analysis_id']
        selected=start_session_collection(self.store,aid,['synthetic-a','synthetic-b'],'Synthetic unknown rate')
        self.assertTrue(selected['collection_readout']['opening'].startswith('Priced usage subtotal:'))
        self.assertIsNone(selected['collection_readout']['usage']['input_tokens']['cost_usd'])

    def test_conflicting_shared_frame_keeps_combined_usage_unknown(self):
        copied=json.loads(self.paths[0].read_text().splitlines()[1])
        copied['sessionId']='synthetic-b';copied['message']['usage']['input_tokens']=999
        with self.paths[1].open('a') as f:f.write(json.dumps(copied)+'\n')
        aid=analyze_dataset(self.store,import_bundle(self.store,self.paths[:2])['dataset_id'])['analysis_id']
        selected=start_session_collection(self.store,aid,['synthetic-a','synthetic-b'],'Synthetic conflicting history')
        self.assertIsNone(selected['collection_readout']['usage']['input_tokens']['value'])
        self.assertTrue(selected['collection_readout']['opening'].startswith('Priced usage subtotal:'))
        self.assertEqual(selected['accounting_coverage']['conflicting_source_identities'],1)

    def test_multiple_file_import_retains_linked_children_and_missing_trace_limits(self):
        parent=linked_fixture(self.root/'synthetic-native')
        aid=analyze_dataset(self.store,import_bundle(self.store,[parent,self.paths[1]])['dataset_id'])['analysis_id']
        selected=start_session_collection(self.store,aid,['session-a','synthetic-b'],'Synthetic children')
        root=get_run(self.store,selected['members'][0]['investigation_id'])
        from ally_analyzer.session_scope import get_scope
        self.assertEqual(get_scope(self.store,root)['agent_ids'],['child-a','child-b','main'])
        self.assertEqual(selected['accounting_coverage']['missing_child_session_ids'],['session-a'])
        self.assertTrue(any('child traces are unavailable' in q for q in selected['collection_readout']['qualifications']))

    def test_review_policy_must_match_original_draft(self):
        self.service.allow_content=False;entries,body=self.prose()
        did=self.call('prepare_collection_reply',sessions=entries,body=body)['draft_id']
        self.service.allow_content=True
        with self.assertRaisesRegex(AnalyzerError,'original disclosure policy'):
            self.call('submit_collection_reply_review',draft_id=did,sessions=entries,body=body,notes='Synthetic policy change',source_checks=[])

    def test_combined_body_allows_per_log_space_and_rejects_overlong_prose_without_editing(self):
        self.read_all();entries,body=self.prose()
        expanded=body+'\n\n'+('Synthetic ' * 500)
        self.assertGreater(len(expanded.split()),450)
        self.assertEqual(self.call('prepare_collection_reply',sessions=entries,body=expanded)['status'],'review_required')
        long=expanded+('Synthetic ' * 150)
        blocked=self.call('prepare_collection_reply',sessions=entries,body=long)
        self.assertEqual(blocked['status'],'needs_revision')
        self.assertIn('default_reply_too_long',{i['code'] for i in blocked['issues']})
        self.assertEqual(records(self.store,self.cid,'collection_reply_draft')[0]['body'],expanded)

    def test_cli_import_multiple_paths_and_collection_start(self):
        script=Path(__file__).resolve().parents[1]/'scripts/ally-session.py'
        base=[sys.executable,str(script),'--data-dir',str(self.store.root)]
        result=subprocess.run([*base,'run',*[str(p) for p in self.paths[:2]]],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        aid=json.loads(result.stdout)['analysis_id']
        result=subprocess.run([*base,'collection-start',aid,'synthetic-a','synthetic-b','--purpose','Synthetic CLI','--mode','individual'],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['output_mode'],'individual')
        with self.assertRaises(AnalyzerError):import_bundle(self.store,[])
        with self.assertRaises(AnalyzerError):import_bundle(self.store,[self.root])
        with self.assertRaises(AnalyzerError):self.service.call('import_bundle',{'path':str(self.paths[0]),'paths':[str(self.paths[1])]})


if __name__=='__main__':unittest.main()
