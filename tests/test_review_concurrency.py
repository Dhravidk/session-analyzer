"""Synthetic cross-process races through the public review persistence paths.

The validation barrier is after real validation and before the final admission.
No persistence method or SQLite connection is mocked. With the previous split
check/save implementation, conflicting workers both passed the stale checks.
"""
import copy
import multiprocessing
from pathlib import Path
import queue
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from ally_analyzer import session_collection, session_reply_review
from ally_analyzer.engine import analyze_dataset
from ally_analyzer.ingest import import_bundle
from ally_analyzer.session_investigation import records
from ally_analyzer.session_scope import start_session_investigation
from ally_analyzer.store import Store
from ally_analyzer.util import AnalyzerError, canonical, utc_now
from tests.helpers import response, write_log
from tests.test_developer_readout import ASSESSMENTS, COMPLIANCE
from tests.test_session_workflow import human


def submit(store, workflow, arguments):
    module = session_reply_review if workflow == 'single' else session_collection
    function = module.submit_session_reply_review if workflow == 'single' else module.submit_collection_reply_review
    return function(store, **arguments)


def concurrent_submit(path, workflow, arguments, barrier, results):
    """Spawn-safe worker: actual Store, validation and persisted public submit."""
    try:
        store = Store(path)
        module = session_reply_review if workflow == 'single' else session_collection
        validate = module.prepare_session_reply
        def synchronized_validation(*args, **kwargs):
            checked = validate(*args, **kwargs)
            barrier.wait(timeout=12)
            return checked
        # An initial barrier also aligns fast idempotent replay paths that do
        # not need validation. The second barrier forces the admission race.
        barrier.wait(timeout=12)
        with patch.object(module, 'prepare_session_reply', synchronized_validation):
            result = submit(store, workflow, arguments)
        results.put({'ok': result})
    except BaseException as exc:
        results.put({'error': type(exc).__name__, 'message': str(exc)})


class ReviewConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ctx = multiprocessing.get_context('spawn')

    def target(self, workflow):
        folder = self.root / workflow
        store = Store(folder/'store')
        source = write_log(folder/'synthetic.jsonl', [human(0, session='synthetic-a'), response(1, session='synthetic-a'),
                                                     human(10, session='synthetic-b'), response(11, session='synthetic-b')])
        aid = analyze_dataset(store, import_bundle(store, source)['dataset_id'])['analysis_id']
        if workflow == 'single':
            iid = start_session_investigation(store, aid, 'synthetic-a', 'Synthetic atomic review')['investigation']['id']
            did = session_reply_review.prepare_reviewed_session_reply(store, iid, ASSESSMENTS, compliance=COMPLIANCE)['draft_id']
            args = {'investigation_id': iid, 'draft_id': did, 'body': ASSESSMENTS, 'compliance': copy.deepcopy(COMPLIANCE),
                    'notes': 'Synthetic atomic review.', 'source_checks': []}
            kind, draft_kind, owner = 'reply_review', 'reply_draft', iid
        else:
            selected = session_collection.start_session_collection(store, aid, ['synthetic-a','synthetic-b'],
                                                                   'Synthetic atomic review', output_mode='combined')
            cid = selected['collection_id']; entries=[]; parts=[]
            for m in selected['members']:
                spans = {name: m['session_id'] + ': ' + text for name, text in COMPLIANCE.items()}
                entries.append({'investigation_id': m['investigation_id'], 'compliance': spans})
                parts.extend(spans.values())
            body = '\n\n'.join(parts)
            did = session_collection.prepare_collection_reply(store, cid, entries, body=body)['draft_id']
            args = {'collection_id':cid, 'draft_id':did, 'body':body, 'sessions':entries,
                    'notes':'Synthetic atomic review.', 'source_checks':[]}
            kind, draft_kind, owner = 'collection_reply_review', 'collection_reply_draft', cid
        with store.connect() as db:
            original = tuple(db.execute('SELECT payload,created_at FROM investigation_records WHERE investigation_id=? AND kind=? AND id=?',
                                         (owner,draft_kind,did)).fetchone())
        return {'store':store, 'workflow':workflow, 'args':args, 'owner':owner, 'kind':kind,
                'draft_kind':draft_kind, 'draft_original':original, 'source':source, 'source_bytes':source.read_bytes()}

    def candidate(self, target, label, valid=True):
        args = copy.deepcopy(target['args'])
        args['notes'] = 'Synthetic review ' + label
        args['body'] = label + '\n\n' + args['body'] if valid else 'Synthetic missing visible assessments ' + label
        return args

    def race(self, target, submissions):
        barrier = self.ctx.Barrier(len(submissions)); results = self.ctx.Queue()
        workers = [self.ctx.Process(target=concurrent_submit,
                    args=(str(target['store'].root),target['workflow'],args,barrier,results)) for args in submissions]
        received=[]; deadline=time.monotonic()+25
        try:
            for worker in workers: worker.start()
            for _ in workers:
                try: received.append(results.get(timeout=max(.01,deadline-time.monotonic())))
                except queue.Empty: self.fail('Concurrent review worker did not return within its deadline')
            for worker in workers:
                worker.join(timeout=max(.01,deadline-time.monotonic()))
                self.assertFalse(worker.is_alive(), 'Concurrent review worker did not stop')
                self.assertEqual(worker.exitcode,0)
        finally:
            for worker in workers:
                if worker.is_alive(): worker.kill()
                if worker.pid is not None: worker.join(timeout=3)
                if worker.pid is not None and not worker.is_alive(): worker.close()
            results.close(); results.join_thread()
        for result in received:
            if 'error' in result: self.assertEqual(result['error'],'AnalyzerError', result)
        return received

    def history(self, target):
        # Reopen the database rather than trusting any worker's return value.
        return records(Store(target['store'].root),target['owner'],target['kind'])

    def retrieve(self, target):
        store = Store(target['store'].root)
        if target['workflow']=='single':
            return session_reply_review.get_reviewed_session_reply(store,target['owner'],target['args']['draft_id'])
        return session_collection.get_reviewed_collection_reply(store,target['owner'],target['args']['draft_id'])

    def assert_retained(self, target):
        self.assertEqual(target['source'].read_bytes(),target['source_bytes'])
        with target['store'].connect() as db:
            current=tuple(db.execute('SELECT payload,created_at FROM investigation_records WHERE investigation_id=? AND kind=? AND id=?',
                                     (target['owner'],target['draft_kind'],target['args']['draft_id'])).fetchone())
        self.assertEqual(current,target['draft_original'])

    def assert_winner(self, target, results):
        accepted=[r for r in self.history(target) if r['status']=='accepted']
        self.assertEqual(len(accepted),1)
        ready=[r['ok'] for r in results if r.get('ok',{}).get('status')=='ready']
        self.assertTrue(ready)
        for item in ready:
            self.assertEqual(item['review_id'],accepted[0]['id'])
            self.assertEqual(item['reply'],accepted[0]['reply'])
        for _ in range(2):
            fetched=self.retrieve(target)
            self.assertEqual(fetched['review_id'],accepted[0]['id'])
            self.assertEqual(fetched['reply'],accepted[0]['reply'])
        self.assertTrue(accepted[0]['reply'].endswith(accepted[0]['submission']['body']))
        self.assert_retained(target)

    def test_conflicting_acceptances_have_one_persisted_winner(self):
        for workflow in ('single','collection'):
            with self.subTest(workflow=workflow):
                target=self.target(workflow)
                results=self.race(target,[self.candidate(target,label) for label in ('A','B')])
                self.assertEqual(sum('ok' in r for r in results),1,results)
                self.assertIn('immutable accepted review',next(r['message'] for r in results if 'error' in r))
                self.assertEqual(len(self.history(target)),1)
                self.assert_winner(target,results)

    def test_identical_concurrent_accepted_retries_reuse_one_review(self):
        for workflow in ('single','collection'):
            with self.subTest(workflow=workflow):
                target=self.target(workflow); args=self.candidate(target,'identical')
                results=self.race(target,[args]*3)
                self.assertTrue(all('ok' in r for r in results),results)
                self.assertEqual(len(self.history(target)),1)
                self.assert_winner(target,results)
                # A retry in yet another process reuses the committed answer.
                replay=self.race(target,[args,args])
                self.assertTrue(all('ok' in r for r in replay),replay)
                self.assertEqual(len(self.history(target)),1)
                self.assert_winner(target,replay)

    def test_identical_rejected_retries_spend_one_slot_and_allow_final_acceptance(self):
        for workflow in ('single','collection'):
            with self.subTest(workflow=workflow):
                target=self.target(workflow); args=self.candidate(target,'identical bad',False)
                results=self.race(target,[args]*3)
                self.assertTrue(all(r.get('ok',{}).get('status')=='needs_revision' for r in results),results)
                self.assertEqual(len({r['ok']['review_id'] for r in results}),1)
                original=self.history(target)[0]
                self.assertEqual(len(self.history(target)),1)
                ready=submit(target['store'],workflow,self.candidate(target,'final good'))
                self.assertEqual(ready['status'],'ready')
                self.assertEqual(len(self.history(target)),2)
                self.assertEqual(self.history(target)[0],original)
                self.assert_winner(target,[{'ok':ready}])

    def test_competing_final_acceptances_cannot_exceed_two_submissions(self):
        for workflow in ('single','collection'):
            with self.subTest(workflow=workflow):
                target=self.target(workflow)
                submit(target['store'],workflow,self.candidate(target,'first rejection',False))
                rejected=self.history(target)[0]
                results=self.race(target,[self.candidate(target,label) for label in ('last A','last B','last C')])
                self.assertEqual(sum('ok' in r for r in results),1,results)
                self.assertEqual(len(self.history(target)),2)
                self.assertIn(rejected,self.history(target))
                self.assert_winner(target,results)

    def test_competing_final_rejections_cannot_create_a_third_attempt(self):
        for workflow in ('single','collection'):
            with self.subTest(workflow=workflow):
                target=self.target(workflow)
                submit(target['store'],workflow,self.candidate(target,'first bad',False))
                results=self.race(target,[self.candidate(target,label,False) for label in ('final bad A','final bad B')])
                self.assertEqual(sum('ok' in r for r in results),1,results)
                self.assertIn('Two review submissions',next(r['message'] for r in results if 'error' in r))
                self.assertEqual(len(self.history(target)),2)
                self.assertEqual({r['status'] for r in self.history(target)},{'rejected'})
                self.assertEqual(self.retrieve(target)['status'],'review_incomplete')
                self.assertNotIn('reply',self.retrieve(target))
                self.assert_retained(target)

    def test_mixed_final_attempts_use_the_same_atomic_slot(self):
        for workflow in ('single','collection'):
            with self.subTest(workflow=workflow):
                target=self.target(workflow)
                submit(target['store'],workflow,self.candidate(target,'first bad',False))
                results=self.race(target,[self.candidate(target,'valid final'),self.candidate(target,'invalid final',False)])
                self.assertEqual(sum('ok' in r for r in results),1,results)
                self.assertEqual(len(self.history(target)),2)
                if any(r['status']=='accepted' for r in self.history(target)): self.assert_winner(target,results)
                else: self.assertEqual(self.retrieve(target)['status'],'review_incomplete')
                self.assert_retained(target)

    def test_failed_append_rolls_back_without_consuming_an_attempt(self):
        for workflow in ('single','collection'):
            with self.subTest(workflow=workflow):
                target=self.target(workflow)
                with target['store'].connect() as db:
                    db.execute("CREATE TRIGGER synthetic_fail_review BEFORE INSERT ON investigation_records WHEN NEW.kind='%s' BEGIN SELECT RAISE(ABORT,'synthetic append failure'); END" % target['kind'])
                args=self.candidate(target,'retry after storage error')
                with self.assertRaisesRegex(sqlite3.IntegrityError,'synthetic append failure'):
                    submit(target['store'],workflow,args)
                self.assertEqual(self.history(target),[])
                with target['store'].connect() as db: db.execute('DROP TRIGGER synthetic_fail_review')
                ready=submit(target['store'],workflow,args)
                self.assertEqual(len(self.history(target)),1)
                self.assert_winner(target,[{'ok':ready}])

    def test_legacy_conflicting_acceptances_are_retained_but_never_return_two_answers(self):
        for workflow in ('single','collection'):
            with self.subTest(workflow=workflow):
                target=self.target(workflow); first=self.candidate(target,'canonical')
                ready=submit(target['store'],workflow,first); original=self.history(target)[0]
                legacy=copy.deepcopy(original);legacy.pop('id')
                legacy_args=self.candidate(target,'legacy conflicting')
                legacy['submission']={key:legacy_args[key] for key in original['submission']}
                legacy['reply']='Synthetic historical conflicting wording, retained byte for byte.'
                with target['store'].connect() as db:
                    db.execute('INSERT INTO investigation_records VALUES (?,?,?,?,?)',
                               (target['owner'],target['kind'],'synthetic_legacy_conflict',canonical(legacy),utc_now()))
                before=self.history(target)
                with target['store'].connect() as db:
                    original_rows=[tuple(r) for r in db.execute('SELECT * FROM investigation_records ORDER BY investigation_id,kind,id')]
                self.assertEqual(self.retrieve(target)['reply'],ready['reply'])
                self.assertEqual(submit(target['store'],workflow,first)['reply'],ready['reply'])
                with self.assertRaisesRegex(AnalyzerError,'immutable accepted review'):
                    submit(target['store'],workflow,legacy_args)
                self.assertEqual(self.history(target),before)
                with target['store'].connect() as db:
                    self.assertEqual([tuple(r) for r in db.execute('SELECT * FROM investigation_records ORDER BY investigation_id,kind,id')],original_rows)
                self.assert_retained(target)


if __name__=='__main__':unittest.main()
