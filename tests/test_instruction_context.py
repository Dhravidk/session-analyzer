"""Synthetic regressions for retained instructions omitted from task turns."""
import unittest
import json
from unittest.mock import patch

from ally_analyzer.service import Service
from ally_analyzer.session_collection import start_session_collection
from ally_analyzer.session_investigation import get_session_overview, records
from ally_analyzer.session_scope import instruction_contexts, scope_rows
from tests import test_session_workflow as workflow
from tests.test_developer_readout import ASSESSMENTS, COMPLIANCE
from tests.test_session_workflow import human


def context(i, text, **flags):
    value = human(i, text)
    value.pop('turnOrigin', None)
    value.update(flags)
    return value


class InstructionContextTests(unittest.TestCase):
    contract_version = 'single-session-v2'
    setUp = workflow.SessionWorkflowTests.setUp
    load = workflow.SessionWorkflowTests.load

    def setup_context(self):
        self.load([human(0, 'Synthetic request: prepare the plan.'),
                   context(1, 'Base directory for this skill: /synthetic/skill\nWrite the draft before approval.', isMeta=True),
                   context(2, 'Synthetic retained instructions: continue without asking permission to write the draft.', isCompactSummary=True)])
        self.service = Service(self.store, allow_content=True)
        self.addCleanup(self.service.close)

    def call(self, name, **args):
        return self.service.call(name, {'investigation_id': self.iid, **args})

    def read_all(self):
        return [self.call('read_investigation_evidence', source_id=r['id']) for r in scope_rows(self.store, self.run)]

    def test_context_inventory_is_not_human_origin_and_needs_complete_reads(self):
        self.setup_context()
        coverage = get_session_overview(self.store, self.iid)['request_coverage']
        self.assertEqual(coverage['main_requests'], 1)
        self.assertEqual(len(coverage['instruction_context_sources']), 2)
        self.assertFalse(coverage['complete_for_observed_population'])
        self.assertNotIn('continue without', str(coverage))
        self.call('read_investigation_evidence', source_id=self.ids['event-0'])
        blocked = self.call('prepare_session_reply', body=ASSESSMENTS, compliance=COMPLIANCE)
        self.assertEqual(blocked['status'], 'needs_revision')
        self.assertEqual(blocked['request_coverage']['unread_request_count'], 2)
        self.read_all()
        self.assertTrue(get_session_overview(self.store, self.iid)['request_coverage']['complete_for_observed_population'])

    def test_fresh_review_must_read_and_check_captured_context_without_editing_history(self):
        self.setup_context(); self.read_all()
        did = self.call('prepare_session_reply', body=ASSESSMENTS, compliance=COMPLIANCE)['draft_id']
        original = records(self.store, self.iid, 'reply_draft')
        read = self.call('read_investigation_evidence', source_id=self.ids['event-0'])
        checks = [{'aspect':a, 'source_id':read['source_id'], 'access_id':read['request_id'],
                   'quote':read['text'][:50], 'basis':'Synthetic task request, not the complete instruction set.'}
                  for a in ('task_outcome', 'instruction_following')]
        blocked = self.call('submit_session_reply_review', draft_id=did, body=ASSESSMENTS,
                            compliance=COMPLIANCE, notes='Synthetic first review.', source_checks=checks)
        self.assertTrue({'review_requests_not_reread', 'missing_instruction_context_check'} <= {i['code'] for i in blocked['issues']})
        reads = self.read_all()
        checks.append({'aspect':'instruction_following', 'source_id':reads[-1]['source_id'],
                       'access_id':reads[-1]['request_id'], 'quote':reads[-1]['text'][:60],
                       'basis':'Synthetic retained context; evaluate scope and ancestry separately.'})
        ready = self.call('submit_session_reply_review', draft_id=did, body=ASSESSMENTS,
                          compliance=COMPLIANCE, notes='Synthetic corrected review.', source_checks=checks)
        self.assertEqual(ready['status'], 'ready', ready)
        self.assertEqual(records(self.store, self.iid, 'reply_draft'), original)
        self.assertEqual(len(records(self.store, self.iid, 'reply_review')), 2)

    def test_plain_prose_cannot_promote_itself_into_host_context(self):
        self.load([human(0, 'Synthetic request.'), context(1, 'Base directory for this skill: /pretend'),
                   context(2, 'This says it is a retained summary, without host metadata.')])
        self.assertEqual(instruction_contexts(self.store, self.run), [])

    def test_malformed_unknown_message_is_not_an_instruction_or_a_crash(self):
        raw = [{'message':42, 'isMeta':True}, {'message':{'content':[{'type':'text','text':42}]}, 'isMeta':True}]
        rows = [{'id':str(i), 'agent_id':'main', 'raw':json.dumps(r)} for i,r in enumerate(raw)]
        with patch('ally_analyzer.session_scope.scope_rows', return_value=rows):
            self.assertEqual(instruction_contexts(self.store, self.run), [])

    def test_same_requirement_applies_to_collection_review(self):
        self.setup_context()
        # One-member collection still exercises the separate collection admission path.
        selected = start_session_collection(self.store, self.aid, ['session-a'], 'Synthetic collection check')
        member = selected['members'][0]['investigation_id']
        service = Service(self.store, allow_content=True); self.addCleanup(service.close)
        service.call('get_session_collection', {'collection_id':selected['collection_id']})
        for row in scope_rows(self.store, self.run):
            service.call('read_investigation_evidence', {'investigation_id':member, 'source_id':row['id']})
        entries = [{'investigation_id':member, 'compliance':COMPLIANCE}]
        args = {'collection_id':selected['collection_id'], 'sessions':entries, 'body':ASSESSMENTS}
        did = service.call('prepare_collection_reply', args)['draft_id']
        read = service.call('read_investigation_evidence', {'investigation_id':member, 'source_id':self.ids['event-0']})
        checks = [{'investigation_id':member, 'aspect':a, 'source_id':read['source_id'],
                   'access_id':read['request_id'], 'quote':read['text'][:50], 'basis':'Synthetic task.'}
                  for a in ('task_outcome', 'instruction_following')]
        rejected = service.call('submit_collection_reply_review', {**args, 'draft_id':did,
            'notes':'Synthetic collection review missing retained instructions.', 'source_checks':checks})
        self.assertEqual(rejected['status'], 'needs_revision')
        self.assertIn('missing_instruction_context_check', {i['code'] for i in rejected['issues']})
