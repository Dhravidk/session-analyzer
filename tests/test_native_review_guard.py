"""Actual SQLite/host-hook regressions, without calling a model."""
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ally_analyzer.native_review import hook_event, launch_state, REVIEWER
from ally_analyzer.store import Store
from ally_analyzer.util import AnalyzerError


def compete(path, ticket, barrier, queue, index):
    store = Store(path)
    barrier.wait(10)
    try:
        hook_event(store, {'hook_event_name':'PreToolUse', 'session_id':'host-' + str(index),
            'tool_use_id':'tool-' + str(index), 'tool_name':'Agent',
            'tool_input':{'subagent_type':REVIEWER, 'prompt':'review_ticket=' + ticket}})
        queue.put('reserved')
    except AnalyzerError:
        queue.put('denied')


class NativeReviewGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.store = Store(self.root/'store')
        self.state = launch_state(self.store, 'owner', 'reply_draft', 'draft')
        self.launch = {'hook_event_name':'PreToolUse', 'session_id':'host', 'tool_use_id':'tool',
            'tool_name':'Agent', 'tool_input':{'subagent_type':REVIEWER,
                'prompt':'review_ticket=' + self.state['ticket']}}

    def test_separate_processes_reserve_only_one_fresh_launch(self):
        ctx = multiprocessing.get_context('spawn')
        barrier, queue = ctx.Barrier(2), ctx.Queue()
        workers = [ctx.Process(target=compete, args=(str(self.store.root), self.state['ticket'], barrier, queue, i)) for i in range(2)]
        try:
            for p in workers: p.start()
            result = [queue.get(timeout=20) for _ in workers]
            for p in workers:
                p.join(20); self.assertEqual(p.exitcode, 0)
            self.assertEqual(sorted(result), ['denied', 'reserved'])
        finally:
            for p in workers:
                if p.is_alive(): p.terminate(); p.join(5)
            queue.close(); queue.join_thread()

    def test_native_identity_is_saved_at_start_and_survives_reopening(self):
        hook_event(self.store, self.launch)
        hook_event(self.store, self.launch)  # Same hook delivery is idempotent.
        hook_event(self.store, {'hook_event_name':'SubagentStart', 'session_id':'host',
            'agent_type':REVIEWER, 'agent_id':'native-one'})
        reopened = Store(self.store.root)
        state = launch_state(reopened, 'owner', 'reply_draft', 'draft')
        self.assertEqual(state['agent_id'], 'native-one')
        self.assertEqual(state['status'], 'started')
        with self.assertRaisesRegex(AnalyzerError, 'only fresh reviewer'):
            hook_event(reopened, {**self.launch, 'tool_use_id':'new-tool'})
        for tool, args in [('Agent', {'resume':'native-one'}), ('SendMessage', {'to':'native-one', 'message':'Continue'})]:
            hook_event(reopened, {**self.launch, 'tool_name':tool, 'tool_input':args})
        with self.assertRaisesRegex(AnalyzerError, 'original host session'):
            hook_event(reopened, {**self.launch, 'session_id':'another-host',
                                  'tool_input':{'resume':'native-one'}})
        with reopened.connect() as db:
            events = [r[0] for r in db.execute('SELECT event FROM reply_reviewer_events ORDER BY id')]
        self.assertEqual(events, ['fresh_launch_reserved', 'native_handle_saved', 'resume_requested', 'resume_requested'])

    def test_pending_without_handle_is_not_reset_or_expired(self):
        hook_event(self.store, self.launch)
        state = launch_state(Store(self.store.root), 'owner', 'reply_draft', 'draft')
        self.assertIsNone(state['agent_id'])
        self.assertIn('do not launch a replacement', state['instruction'])
        with self.assertRaises(AnalyzerError):
            hook_event(self.store, {**self.launch, 'tool_use_id':'retry'})

    def test_unknown_ticket_or_unreserved_native_start_fails(self):
        with self.assertRaises(AnalyzerError):
            hook_event(self.store, {**self.launch, 'tool_input':{'subagent_type':REVIEWER, 'prompt':'No ticket'}})
        with self.assertRaises(AnalyzerError):
            hook_event(self.store, {'hook_event_name':'SubagentStart', 'session_id':'host', 'agent_type':REVIEWER, 'agent_id':'unreserved'})
        self.assertEqual(hook_event(self.store, {**self.launch, 'tool_input':{'subagent_type':'other'}}), {})

    def test_resume_tool_policy_requires_explicit_persisted_identity(self):
        from ally_analyzer.claude_runner import audit_tool_policy
        trace = self.root/'empty.jsonl'; trace.write_text('')
        for tool, args in [('Agent', {'resume':'native-one'}), ('SendMessage', {'to':'native-one'})]:
            call = {'id':'synthetic-resume', 'name':tool, 'input':args}
            self.assertFalse(audit_tool_policy([call], trace, [])['executed_calls_within_policy'])
            self.assertTrue(audit_tool_policy([call], trace, [], allowed_agent_ids=['native-one'])['executed_calls_within_policy'])

    def test_historical_accepted_wording_is_preserved_and_cannot_buy_a_new_review(self):
        from ally_analyzer.session_investigation import put_record, records
        historical = {'draft_id':'draft', 'status':'accepted', 'submission':{'body':'Exact synthetic authored wording.'}}
        put_record(self.store, {'id':'owner'}, 'reply_review', historical)
        before = records(self.store, 'owner', 'reply_review')
        with self.assertRaisesRegex(AnalyzerError, 'accepted answer'):
            hook_event(self.store, self.launch)
        self.assertEqual(records(self.store, 'owner', 'reply_review'), before)

    def test_malformed_hook_input_fails_closed(self):
        script = Path(__file__).resolve().parents[1]/'scripts/reviewer_hook.py'
        for text in ('[]', 'malformed'):
            result = subprocess.run([sys.executable, str(script)], input=text,
                capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_real_hook_process_denies_duplicate_before_an_agent_can_start(self):
        script = Path(__file__).resolve().parents[1]/'scripts/reviewer_hook.py'
        env = dict(os.environ, ALLY_ANALYZER_HOME=str(self.store.root))
        def send(payload):
            result = subprocess.run([sys.executable, str(script)], input=json.dumps(payload),
                capture_output=True, text=True, env=env, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertEqual(send(self.launch), {})
        denied = send({**self.launch, 'tool_use_id':'competing'})
        self.assertEqual(denied['hookSpecificOutput']['permissionDecision'], 'deny')
        # The guard never creates or edits a model-authored draft/review.
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM investigation_records').fetchone()[0], 0)
