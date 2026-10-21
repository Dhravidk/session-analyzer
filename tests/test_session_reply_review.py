"""Offline workflow tests on explicitly synthetic evidence, never a live host."""
import copy
import hashlib
import unittest

from ally_analyzer.claude_runner import audit_tool_policy
from ally_analyzer.service import Service
from ally_analyzer.session_investigation import records
from ally_analyzer.session_scope import scope_rows
from ally_analyzer.util import AnalyzerError
from tests import test_session_workflow as workflow
from tests.helpers import response
from tests.test_developer_readout import ASSESSMENTS, COMPLIANCE, queued_update
from tests.test_session_workflow import human


class SessionReplyReviewTests(unittest.TestCase):
    contract_version = 'single-session-v2'
    setUp = workflow.SessionWorkflowTests.setUp
    load = workflow.SessionWorkflowTests.load

    def setup_service(self, content=True):
        self.load([human(0, 'Synthetic request: write a draft; obtain approval before implementation.'),
                   queued_update(1, 'Synthetic update: include the second module.'),
                   response(2, content=[{'type':'text','text':'Synthetic ending: the draft remains unwritten.'}])])
        self.service = Service(self.store, allow_content=content)
        self.addCleanup(self.service.close)
        self.reads = [self.invoke('read_investigation_evidence', source_id=r['id'])
                      for r in scope_rows(self.store, self.run)] if content else []

    def invoke(self, name, **kwargs):
        return self.service.call(name, {'investigation_id':self.iid, **kwargs})

    def draft(self, body=ASSESSMENTS):
        return self.invoke('prepare_session_reply', body=body, compliance=COMPLIANCE)

    def source_checks(self):
        if not self.reads:
            return []
        read = self.reads[0]
        return [{'aspect':aspect, 'source_id':read['source_id'], 'access_id':read['request_id'],
                 'quote':read['text'][:60], 'basis':'Synthetic evidence of the request; not proof of completion.'}
                for aspect in ('task_outcome', 'instruction_following')]

    def submit(self, draft_id, **kwargs):
        args = {'draft_id':draft_id, 'body':ASSESSMENTS, 'compliance':COMPLIANCE,
                'notes':'Synthetic reviewer notes: preserve unknown outcomes.', 'source_checks':self.source_checks()}
        args.update(kwargs)
        return self.invoke('submit_session_reply_review', **args)

    def reread(self):
        self.reads = [self.invoke('read_investigation_evidence', source_id=r['id'])
                      for r in scope_rows(self.store, self.run)]

    def test_default_cannot_be_ready_without_saved_source_review(self):
        self.setup_service()
        result = self.draft()
        self.assertEqual(result['status'], 'review_required')
        self.assertNotIn('reply', result)
        fetched = self.invoke('get_reviewed_session_reply', draft_id=result['draft_id'])
        self.assertNotIn('reply', fetched)
        draft = self.invoke('get_session_reply_draft', draft_id=result['draft_id'])
        self.assertEqual(draft['review_request_coverage']['unread_request_count'], 2)
        self.assertTrue(draft['draft_content_withheld'])
        self.assertNotIn('body', draft['draft'])
        self.reread()
        shown = self.invoke('get_session_reply_draft', draft_id=result['draft_id'])
        self.assertFalse(shown['draft_content_withheld'])
        self.assertEqual(shown['draft']['body'], ASSESSMENTS)

    def test_review_requires_fresh_requests_updates_and_literal_sources(self):
        self.setup_service()
        draft_id = self.draft()['draft_id']
        blocked = self.submit(draft_id)
        self.assertEqual(blocked['status'], 'needs_revision')
        self.assertNotIn('reply', blocked)
        self.assertIn('review_requests_not_reread', {i['code'] for i in blocked['issues']})
        self.assertIn('invalid_review_source', {i['code'] for i in blocked['issues']})
        # Same reviewer resumes this draft; the original attempt stays saved.
        self.reread()
        ready = self.submit(draft_id)
        self.assertEqual(ready['status'], 'ready')
        self.assertEqual(len(records(self.store, self.iid, 'reply_review')), 2)
        self.assertTrue(ready['reply'].endswith(ASSESSMENTS))

    def test_reviewed_revision_is_exact_and_original_draft_is_unchanged(self):
        self.setup_service()
        original = 'Synthetic initial recommendation.\n\n' + ASSESSMENTS
        draft_id = self.draft(original)['draft_id']
        before = copy.deepcopy(records(self.store, self.iid, 'reply_draft'))
        self.reread()
        revised = 'Synthetic supported check, after source review.\n\n' + ASSESSMENTS
        submitted = self.submit(draft_id, body=revised)
        self.assertEqual(submitted['status'], 'ready')
        fetched = self.invoke('get_reviewed_session_reply', draft_id=draft_id)
        self.assertEqual(fetched['reply'], submitted['reply'])
        self.assertTrue(fetched['reply'].endswith(revised))
        self.assertEqual(records(self.store, self.iid, 'reply_draft'), before)
        history = self.invoke('get_session_reply_draft', draft_id=draft_id, include_reviews=True)['review_history']
        self.assertEqual(history[0]['submission']['body'], revised)
        self.assertEqual(records(self.store, self.iid, 'incident'), [])
        again = self.draft(original)
        self.assertEqual(again['draft_id'], draft_id)
        self.assertEqual(again['reply'], fetched['reply'])
        changed = self.draft('Different synthetic answer.\n\n' + ASSESSMENTS)
        self.assertNotEqual(changed['draft_id'], draft_id)
        self.assertEqual(changed['status'], 'review_required')

    def test_reviewed_body_cannot_opt_into_unrequested_topics(self):
        self.setup_service()
        draft_id = self.draft()['draft_id']; self.reread()
        result = self.submit(draft_id, body='Use one-hour prompt caching.\n\n' + ASSESSMENTS)
        self.assertEqual(result['issues'][0]['code'], 'unrequested_cache_detail')
        stopped = self.invoke('get_reviewed_session_reply', draft_id=draft_id)
        self.assertNotIn('reply', stopped)
        self.assertEqual(stopped['status'], 'review_required')

    def test_search_snippet_or_fabricated_quote_cannot_support_review(self):
        self.setup_service()
        draft_id = self.draft()['draft_id']; self.reread()
        checks = self.source_checks(); checks[0]['quote'] = 'Invented evidence that never occurred.'
        rejected = self.submit(draft_id, source_checks=checks)
        self.assertIn('invalid_review_source', {i['code'] for i in rejected['issues']})
        search = self.invoke('search_investigation_text', query='Synthetic request')
        checks = self.source_checks(); checks[0]['access_id'] = search['request_id']
        result = self.submit(draft_id, source_checks=checks)
        self.assertIn('invalid_review_source', {i['code'] for i in result['issues']})

    def test_reading_requests_does_not_substitute_for_review_assessments(self):
        self.setup_service()
        draft_id = self.draft()['draft_id']; self.reread()
        result = self.submit(draft_id, source_checks=[])
        self.assertEqual({i['code'] for i in result['issues']},
                         {'missing_review_task_outcome_source', 'missing_review_instruction_following_source'})

    def test_invalid_source_attempt_is_retained_instead_of_resetting_review(self):
        self.setup_service()
        draft_id = self.draft()['draft_id']; self.reread()
        checks = self.source_checks(); checks[0]['source_id'] = 'synthetic-outside-scope'
        result = self.submit(draft_id, source_checks=checks)
        self.assertEqual(result['status'], 'needs_revision')
        self.assertIn('invalid_review_source', {i['code'] for i in result['issues']})
        self.assertEqual(len(records(self.store, self.iid, 'reply_review')), 1)

    def test_review_is_bounded_and_replay_does_not_spend_another_attempt(self):
        self.setup_service()
        draft_id = self.draft()['draft_id']; self.reread()
        first = self.submit(draft_id, source_checks=[])
        repeated = self.submit(draft_id, source_checks=[])
        self.assertEqual(repeated['review_id'], first['review_id'])
        self.assertEqual(len(records(self.store, self.iid, 'reply_review')), 1)
        self.submit(draft_id, source_checks=[], notes='Second synthetic failed review.')
        with self.assertRaisesRegex(AnalyzerError, 'Two review submissions'):
            self.submit(draft_id, notes='Unbounded third attempt.')
        stopped = self.invoke('get_reviewed_session_reply', draft_id=draft_id)
        self.assertNotIn('reply', stopped)
        self.assertEqual(stopped['status'], 'review_incomplete')

    def test_metadata_only_review_never_requires_or_leaks_source_quotes(self):
        self.setup_service(content=False)
        draft_id = self.draft()['draft_id']
        self.assertFalse(self.invoke('get_session_reply_draft', draft_id=draft_id)['draft_content_withheld'])
        ready = self.submit(draft_id, source_checks=[])
        self.assertEqual(ready['status'], 'ready')
        review = records(self.store, self.iid, 'reply_review')[0]
        self.assertEqual(review['review_mode'], 'metadata_only')
        self.assertIn('unverified', ready['reply'])

    def test_current_disclosure_cannot_fetch_a_content_enabled_draft(self):
        self.setup_service()
        draft_id = self.draft()['draft_id']
        self.service.allow_content = False
        for name in ('get_session_reply_draft', 'get_reviewed_session_reply'):
            with self.subTest(tool=name), self.assertRaises(AnalyzerError):
                self.invoke(name, draft_id=draft_id)

    def test_draft_scope_and_accepted_review_are_immutable(self):
        self.setup_service()
        draft_id = self.draft()['draft_id']; self.reread()
        self.submit(draft_id)
        with self.assertRaisesRegex(AnalyzerError, 'immutable accepted review'):
            self.submit(draft_id, body='Replacement.\n\n' + ASSESSMENTS)
        with self.assertRaises(AnalyzerError):
            self.invoke('get_reviewed_session_reply', draft_id='reply_draft_wrong_scope')

    def test_ready_transport_hash_preserves_author_punctuation_and_history(self):
        self.setup_service(content=False)
        body='Keep the author’s text (including this); do not split it.\n\n'+ASSESSMENTS
        did=self.draft(body)['draft_id']
        ready=self.submit(did,body=body,source_checks=[])
        self.assertEqual(ready['status'],'ready')
        expected=hashlib.sha256(ready['reply'].encode('utf-8')).hexdigest()
        self.assertEqual(ready['delivery']['reply_sha256'],expected)
        self.assertEqual(ready['delivery']['reply_characters'],len(ready['reply']))
        self.assertTrue(ready['reply'].endswith(body))
        saved=records(self.store,self.iid,'reply_review')
        fetched=self.invoke('get_reviewed_session_reply',draft_id=did)
        self.assertEqual(fetched['delivery'],ready['delivery'])
        self.assertEqual(fetched['reply'],saved[0]['reply'])
        self.assertEqual(records(self.store,self.iid,'reply_review'),saved)

    def test_legacy_draft_view_keeps_its_original_wording_available(self):
        from ally_analyzer.session_investigation import put_record
        self.setup_service()
        did=self.draft()['draft_id']
        original=records(self.store,self.iid,'reply_draft')[0]
        legacy={k:v for k,v in original.items() if k!='id'}
        legacy['contract_version']='source-review-v1'
        old=put_record(self.store,{'id':self.iid},'reply_draft',legacy)
        self.assertTrue(self.invoke('get_session_reply_draft',draft_id=did)['draft_content_withheld'])
        view=self.invoke('get_session_reply_draft',draft_id=old)
        self.assertFalse(view['draft_content_withheld'])
        self.assertEqual(view['draft']['body'],original['body'])

    def test_agent_auditor_allows_only_the_packaged_reviewer(self):
        self.setup_service(content=False)
        trace = self.store.root / 'synthetic-empty-transcript.jsonl'; trace.write_text('')
        def audit(kind, agents=()):
            return audit_tool_policy([{'id':'synthetic-tool', 'name':'Agent', 'input':{'subagent_type':kind}}],
                                      trace, [], allowed_agents=agents)['executed_calls_within_policy']
        self.assertFalse(audit('ally-session-analyzer:source-review'))
        self.assertTrue(audit('ally-session-analyzer:source-review', ('ally-session-analyzer:source-review',)))
        self.assertFalse(audit('general-purpose', ('ally-session-analyzer:source-review',)))
