"""Synthetic draft-registration races with real cross-process SQLite writes.

A forwarding append hook observes the captured markers. It pauses the old
nontransactional writer until a second process has prepared after later reads.
Inside a transaction it does not wait for that competing writer (which would
block on SQLite). Every append still executes the original persistence code.
"""
import copy
from contextlib import ExitStack
import multiprocessing
from pathlib import Path
import queue
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from ally_analyzer import reply_review, session_collection, session_investigation, session_reply_review
from ally_analyzer.engine import analyze_dataset
from ally_analyzer.ingest import import_bundle
from ally_analyzer.session_investigation import get_session_overview, put_record, record_by_id, records
from ally_analyzer.session_scope import get_run, read_investigation_evidence, scope_rows, start_session_investigation
from ally_analyzer.store import Store
from tests.helpers import response, write_log
from tests.test_developer_readout import ASSESSMENTS, COMPLIANCE
from tests.test_session_workflow import human


def boundary(draft):
    return {name: copy.deepcopy(draft[name]) for name in ('after_access_id','after_access_ids') if name in draft}


def prepare(store, workflow, args):
    function = (session_reply_review.prepare_reviewed_session_reply if workflow == 'single'
                else session_collection.prepare_collection_reply)
    return function(store, **args)


def read_sources(store, investigation_ids):
    checks=[]
    for iid in investigation_ids:
        for row in scope_rows(store,get_run(store,iid)):
            read=read_investigation_evidence(store,iid,row['id'],allow_content=True)
            aspect='instruction_following' if row['kind']=='user' else 'task_outcome'
            checks.append({'investigation_id':iid, 'source_id':row['id'], 'access_id':read['request_id'],
                           'aspect':aspect, 'quote':read['text'][:70], 'basis':'Synthetic source; no semantic certificate.'})
    return checks


def registration_worker(path, workflow, kind, owner, ids, args, role, captured, second_done, results):
    try:
        store=Store(path); observed={}
        original=session_investigation.put_record
        def forwarding_append(store,run,record_kind,body,*,connection=None):
            if role==0 and record_kind==kind:
                observed['captured_boundary']=boundary(body)
                observed['writer_transaction']=bool(connection is not None and connection.in_transaction)
                captured.set()
                if not observed['writer_transaction'] and not second_done.wait(timeout=12):
                    raise TimeoutError('Synthetic second preparer did not finish')
            return original(store,run,record_kind,body,connection=connection)
        with ExitStack() as stack:
            # Older workflows import put_record directly; the new helper owns
            # that call. Both hooks forward to the same actual SQLite append.
            for module in (session_reply_review,session_collection,reply_review):
                if hasattr(module,'put_record'):
                    stack.enter_context(patch.object(module,'put_record',forwarding_append))
            if role==1:
                if not captured.wait(timeout=12): raise TimeoutError('Synthetic first marker was not captured')
                if args['allow_content']:
                    read_sources(store,ids)
                else:
                    for iid in ids:get_session_overview(store,iid)
                with store.connect() as db:
                    observed['later_access_ids']={iid:db.execute('SELECT MAX(id) FROM investigation_access WHERE investigation_id=?',(iid,)).fetchone()[0] for iid in ids}
            result=prepare(store,workflow,args)
            saved=record_by_id(store,owner,kind,result['draft_id'])
        results.put({'role':role,'result':result,'draft':saved,**observed})
    except BaseException as exc:
        results.put({'role':role,'error':type(exc).__name__,'message':str(exc)})
    finally:
        if role==1: second_done.set()


class DraftRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.ctx=multiprocessing.get_context('spawn')

    def target(self, workflow, *, content=True, mode='combined'):
        folder=Path(tempfile.mkdtemp(prefix='synthetic-'+workflow+'-',dir=self.root))
        store=Store(folder/'store')
        rows=[human(0,'Synthetic request: draft a plan; await implementation approval.',session='synthetic-a'),
              response(1,session='synthetic-a'),human(10,'Synthetic request: inspect a second plan.',session='synthetic-b'),
              response(11,session='synthetic-b')]
        source=write_log(folder/'synthetic.jsonl',rows)
        aid=analyze_dataset(store,import_bundle(store,source)['dataset_id'])['analysis_id']
        if workflow=='single':
            owner=start_session_investigation(store,aid,'synthetic-a','Synthetic atomic draft registration')['investigation']['id']
            ids=[owner];kind='reply_draft'
            args={'investigation_id':owner,'body':ASSESSMENTS,'compliance':copy.deepcopy(COMPLIANCE),'allow_content':content}
        else:
            selected=session_collection.start_session_collection(store,aid,['synthetic-a','synthetic-b'],
                        'Synthetic atomic draft registration',output_mode=mode)
            owner=selected['collection_id'];ids=[];entries=[];parts=[];kind='collection_reply_draft'
            for m in selected['members']:
                spans={name:m['session_id']+': '+text for name,text in COMPLIANCE.items()}
                entry={'investigation_id':m['investigation_id'],'compliance':spans}
                if mode=='individual': entry['body']='\n'.join(spans.values())
                entries.append(entry);parts.extend(spans.values());ids.append(m['investigation_id'])
            args={'collection_id':owner,'sessions':entries,'allow_content':content}
            if mode=='combined':args['body']='\n\n'.join(parts)
        pre_reads=read_sources(store,ids) if content else []
        return {'store':store,'workflow':workflow,'owner':owner,'ids':ids,'kind':kind,'args':args,'pre_reads':pre_reads,
                'source':source,'original_source':source.read_bytes()}

    def pair(self, target, second_args=None):
        captured=self.ctx.Event();second_done=self.ctx.Event();results=self.ctx.Queue()
        args_list=[target['args'],second_args or target['args']]
        workers=[self.ctx.Process(target=registration_worker,args=(str(target['store'].root),target['workflow'],target['kind'],
                  target['owner'],target['ids'],args,role,captured,second_done,results)) for role,args in enumerate(args_list)]
        returned=[];deadline=time.monotonic()+25
        try:
            for worker in workers:worker.start()
            for _ in workers:
                try:returned.append(results.get(timeout=max(.01,deadline-time.monotonic())))
                except queue.Empty:self.fail('Draft-registration process exceeded its deadline')
            for worker in workers:
                worker.join(timeout=max(.01,deadline-time.monotonic()))
                self.assertFalse(worker.is_alive());self.assertEqual(worker.exitcode,0)
        finally:
            for worker in workers:
                if worker.is_alive():worker.kill()
                if worker.pid is not None:worker.join(timeout=3)
                if worker.pid is not None and not worker.is_alive():worker.close()
            results.close();results.join_thread()
        self.assertTrue(all('error' not in r for r in returned),returned)
        return sorted(returned,key=lambda r:r['role'])

    def drafts(self, target):
        return records(Store(target['store'].root),target['owner'],target['kind'])

    def raw_records(self, target):
        with target['store'].connect() as db:
            return [tuple(r) for r in db.execute('SELECT * FROM investigation_records ORDER BY investigation_id,kind,id')]

    def get_draft(self, target, did, *, reviews=False):
        if target['workflow']=='single':
            return session_reply_review.get_session_reply_draft(target['store'],target['owner'],did,
                        allow_content=target['args']['allow_content'],include_reviews=reviews)
        return session_collection.get_collection_reply_draft(target['store'],target['owner'],did,
                        allow_content=target['args']['allow_content'],include_reviews=reviews)

    def submit(self, target, did, checks, *, valid=True, label='Synthetic review'):
        args=copy.deepcopy(target['args']);args['draft_id']=did;args['notes']=label
        if target['workflow']=='single':
            args['source_checks']=[{k:v for k,v in c.items() if k!='investigation_id'} for c in checks]
            if not valid:args['body']='Synthetic missing assessment.'
            return session_reply_review.submit_session_reply_review(target['store'],**args)
        args['source_checks']=checks
        if not valid:
            if 'body' in args:args['body']='Synthetic missing assessments.'
            else:
                for entry in args['sessions']:entry['body']='Synthetic missing assessments.'
        return session_collection.submit_collection_reply_review(target['store'],**args)

    def assert_same_registration(self, target, returned):
        saved=self.drafts(target)
        self.assertEqual(len(saved),1,saved)
        self.assertEqual({r['result']['draft_id'] for r in returned},{saved[0]['id']})
        self.assertTrue(returned[0]['writer_transaction'])
        self.assertEqual(boundary(saved[0]),returned[0]['captured_boundary'])
        markers=({target['owner']:saved[0]['after_access_id']} if target['workflow']=='single' else saved[0]['after_access_ids'])
        # The second process really read later sources. The old implementation
        # captured those later markers into a second draft with the same key.
        self.assertTrue(all(returned[1]['later_access_ids'][iid]>marker for iid,marker in markers.items()))
        self.assertEqual(target['source'].read_bytes(),target['original_source'])

    def test_concurrent_identical_preparations_share_winning_draft(self):
        for workflow in ('single','collection'):
            with self.subTest(workflow=workflow):
                target=self.target(workflow);self.assert_same_registration(target,self.pair(target))

    def test_individual_collection_uses_the_same_registration_gate(self):
        target=self.target('collection',mode='individual')
        self.assert_same_registration(target,self.pair(target))

    def test_reopening_and_retrying_keeps_original_markers_and_fresh_reads(self):
        for workflow in ('single','collection'):
            with self.subTest(workflow=workflow):
                target=self.target(workflow)
                did=prepare(target['store'],workflow,target['args'])['draft_id'];saved=self.drafts(target)[0]
                read_sources(target['store'],target['ids']);before=self.raw_records(target)
                target['store']=Store(target['store'].root)
                retried=prepare(target['store'],workflow,target['args'])
                self.assertEqual(retried['draft_id'],did)
                self.assertEqual(self.drafts(target),[saved]);self.assertEqual(self.raw_records(target),before)
                coverage=self.get_draft(target,did)['review_request_coverage']
                coverages=[coverage] if workflow=='single' else coverage.values()
                self.assertTrue(all(c['unread_request_count']==0 for c in coverages))

    def test_concurrent_distinct_content_and_policies_remain_distinct(self):
        for workflow in ('single','collection'):
            for change in ('body','allow_content'):
                with self.subTest(workflow=workflow,change=change):
                    target=self.target(workflow);other=copy.deepcopy(target['args'])
                    if change=='body':other['body']='Synthetic different draft.\n\n'+other['body']
                    else:other['allow_content']=False
                    returned=self.pair(target,other);saved=self.drafts(target)
                    self.assertEqual(len(saved),2)
                    self.assertEqual(len({r['draft_key'] for r in saved}),2)
                    self.assertEqual(len({r['result']['draft_id'] for r in returned}),2)
                    if change=='allow_content':self.assertEqual({d['allow_content'] for d in saved},{True,False})

    def test_preboundary_reads_are_not_credited_and_review_history_survives_retries(self):
        for workflow in ('single','collection'):
            with self.subTest(workflow=workflow):
                target=self.target(workflow)
                did=prepare(target['store'],workflow,target['args'])['draft_id'];saved=self.drafts(target)[0]
                blocked=self.submit(target,did,target['pre_reads'])
                self.assertEqual(blocked['status'],'needs_revision')
                self.assertIn('invalid_review_source',{i['code'] for i in blocked['issues']})
                self.assertIn('review_requests_not_reread',{i['code'] for i in blocked['issues']})
                before=self.raw_records(target);target['store']=Store(target['store'].root)
                self.assertEqual(prepare(target['store'],workflow,target['args'])['draft_id'],did)
                self.assertEqual(self.raw_records(target),before)
                self.assertEqual(self.drafts(target),[saved])
                coverage=self.get_draft(target,did)['review_request_coverage']
                self.assertTrue(all(c['unread_request_count']>0 for c in ([coverage] if workflow=='single' else coverage.values())))
                fresh=read_sources(target['store'],target['ids']);ready=self.submit(target,did,fresh)
                self.assertEqual(ready['status'],'ready',ready)
                before=self.raw_records(target)
                replay=prepare(Store(target['store'].root),workflow,target['args'])
                self.assertEqual(replay['draft_id'],did);self.assertEqual(replay['reply'],ready['reply'])
                self.assertEqual(self.raw_records(target),before);self.assertEqual(self.drafts(target),[saved])
                self.assertEqual(len(self.get_draft(target,did,reviews=True)['review_history']),2)

    def test_legacy_duplicates_keep_canonical_boundary_and_independent_reviews(self):
        for workflow in ('single','collection'):
            for canonical_accepted in (False,True):
                with self.subTest(workflow=workflow,canonical_accepted=canonical_accepted):
                    target=self.target(workflow,content=False)
                    did=prepare(target['store'],workflow,target['args'])['draft_id'];first=self.drafts(target)[0]
                    self.submit(target,did,[],valid=canonical_accepted,label='Synthetic canonical review')
                    duplicate={k:copy.deepcopy(v) for k,v in first.items() if k!='id'}
                    if workflow=='single':duplicate['after_access_id']+=1
                    else:duplicate['after_access_ids']={iid:n+1 for iid,n in duplicate['after_access_ids'].items()}
                    other=put_record(target['store'],{'id':target['owner']},target['kind'],duplicate)
                    self.assertNotEqual(other,did)
                    self.submit(target,other,[],valid=not canonical_accepted,label='Synthetic independent legacy review')
                    before=self.raw_records(target)
                    replay=prepare(Store(target['store'].root),workflow,target['args'])
                    self.assertEqual(replay['draft_id'],did)
                    self.assertEqual(replay['status'],'ready' if canonical_accepted else 'review_required')
                    self.assertEqual(self.raw_records(target),before)
                    self.assertEqual(boundary(self.get_draft(target,did)['draft']),boundary(first))
                    self.assertEqual(boundary(self.get_draft(target,other)['draft']),boundary(duplicate))
                    self.assertEqual(len(self.get_draft(target,did,reviews=True)['review_history']),1)
                    self.assertEqual(len(self.get_draft(target,other,reviews=True)['review_history']),1)

    def test_failed_registration_rolls_back_without_leaving_a_partial_draft(self):
        for workflow in ('single','collection'):
            with self.subTest(workflow=workflow):
                target=self.target(workflow)
                with target['store'].connect() as db:
                    db.execute("CREATE TRIGGER synthetic_fail_draft BEFORE INSERT ON investigation_records WHEN NEW.kind='%s' BEGIN SELECT RAISE(ABORT,'synthetic registration failure'); END" % target['kind'])
                with self.assertRaisesRegex(sqlite3.IntegrityError,'synthetic registration failure'):
                    prepare(target['store'],workflow,target['args'])
                self.assertEqual(self.drafts(target),[])
                read_sources(target['store'],target['ids'])
                with target['store'].connect() as db:db.execute('DROP TRIGGER synthetic_fail_draft')
                did=prepare(target['store'],workflow,target['args'])['draft_id']
                self.assertEqual(len(self.drafts(target)),1)
                self.assertEqual(self.drafts(target)[0]['id'],did)
                coverage=self.get_draft(target,did)['review_request_coverage']
                self.assertTrue(all(c['unread_request_count']>0 for c in ([coverage] if workflow=='single' else coverage.values())))


if __name__=='__main__':unittest.main()
