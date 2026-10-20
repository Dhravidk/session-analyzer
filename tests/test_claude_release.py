"""Synthetic trace/parser and interruption checks; these never invoke Claude."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

from scripts.test_claude_release import REVIEWER, interruption_point, native_request_coverage, reviewer_activity, run_stage
from ally_analyzer.engine import analyze_dataset
from ally_analyzer.ingest import import_bundle
from ally_analyzer.session_scope import get_run, read_investigation_evidence, scope_rows, start_session_investigation
from ally_analyzer.store import Store
from tests.helpers import response, write_log
from tests.test_session_workflow import human


def message(content, *, parent=None, agent=None, usage=None, mid=None):
    row = {'type': 'assistant', 'message': {'role': 'assistant', 'content': content}}
    if parent: row['parent_tool_use_id'] = parent
    if agent: row['agent_id'] = agent
    if usage is not None: row['message']['usage'] = usage
    if mid: row['message']['id'] = mid
    return row


def call(cid, name, value):
    return {'type': 'tool_use', 'id': cid, 'name': name, 'input': value}


def result(cid, value):
    return message([{'type': 'tool_result', 'tool_use_id': cid, 'content': json.dumps(value)}])


def native_rows():
    return [message([call('launch', 'Agent', {'subagent_type': REVIEWER})]),
            message([call('read', 'mcp__scope__read_investigation_evidence', {})],
                    parent='launch', agent='native-a', mid='msg-a', usage={'input_tokens': 4, 'output_tokens': 20}),
            result('read', {'request_id': 'fresh-read', 'text_sha256': 'synthetic', 'text': 'Synthetic source'}),
            message([call('submit', 'mcp__scope__submit_collection_reply_review', {})],
                    parent='launch', agent='native-a', mid='msg-b', usage={'input_tokens': 4, 'output_tokens': 50}),
            result('submit', {'status': 'ready', 'review_id': 'accepted-review'})]


class ClaudeReleaseTests(unittest.TestCase):
    def test_native_linkage_and_model_usage_count(self):
        activity = reviewer_activity(native_rows())
        self.assertEqual(activity['fresh_reviewer_launches'], 1)
        self.assertEqual(activity['observed_reviewer_model_responses'], 2)
        self.assertEqual(activity['agent_ids'], ['native-a'])
        self.assertEqual(activity['accepted_native_review_ids'], ['accepted-review'])
        self.assertEqual(activity['source_read_request_ids'], ['fresh-read'])

    def test_duplicate_stream_frames_are_not_extra_paid_requests(self):
        rows = native_rows()
        updated = copy.deepcopy(rows[1]); updated['message']['usage']['output_tokens'] = 30
        activity = reviewer_activity(rows + [rows[1], updated])
        self.assertEqual(activity['agent_call_count'], 1)
        self.assertEqual(activity['observed_reviewer_model_responses'], 2)
        self.assertEqual(activity['model_responses'][0]['usage']['output_tokens'], 30)

    def test_resume_without_redundant_type_preserves_one_identity(self):
        rows = native_rows() + [message([call('resume', 'Agent', {'resume': 'native-a'})]),
            message([], parent='resume', agent='native-a', mid='msg-c', usage={'input_tokens': 3})]
        activity = reviewer_activity(rows)
        self.assertEqual(activity['fresh_reviewer_launches'], 1)
        self.assertEqual(activity['resume_calls'], 1)
        self.assertEqual(activity['agent_ids'], ['native-a'])
        self.assertEqual(activity['observed_reviewer_model_responses'], 3)

    def test_parent_or_unrelated_submission_cannot_establish_native_review(self):
        rows = [message([call('submit', 'mcp__scope__submit_session_reply_review', {})]),
                result('submit', {'status': 'ready', 'review_id': 'parent-review'}),
                message([call('other', 'Agent', {'subagent_type': 'other'})]),
                message([], parent='other', agent='other-a', mid='msg-other', usage={'input_tokens': 9})]
        activity = reviewer_activity(rows)
        self.assertEqual(activity['agent_ids'], [])
        self.assertEqual(activity['accepted_native_review_ids'], [])
        self.assertEqual(activity['observed_reviewer_model_responses'], 0)
        self.assertIsNone(interruption_point(rows))

    def test_second_fresh_reviewer_remains_visible(self):
        rows = native_rows() + [message([call('extra', 'Agent', {'subagent_type': REVIEWER})]),
                message([], parent='extra', agent='native-b', mid='msg-other', usage={'input_tokens': 9})]
        activity = reviewer_activity(rows)
        self.assertEqual(activity['fresh_reviewer_launches'], 2)
        self.assertEqual(activity['agent_ids'], ['native-a', 'native-b'])

    def test_only_fresh_native_reads_count_towards_independent_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); store = Store(root / 'store')
            source = write_log(root / 'synthetic.jsonl', [human(0, 'Synthetic task.'), response(1)])
            aid = analyze_dataset(store, import_bundle(store, source)['dataset_id'])['analysis_id']
            iid = start_session_investigation(store, aid, 'session-a', 'Synthetic native coverage')['investigation']['id']
            source_ids = [r['id'] for r in scope_rows(store, get_run(store, iid))]
            earlier = [read_investigation_evidence(store, iid, sid, allow_content=True)['request_id'] for sid in source_ids]
            with store.connect() as db:
                marker = db.execute('SELECT MAX(id) FROM investigation_access WHERE investigation_id=?', (iid,)).fetchone()[0]
            later = [read_investigation_evidence(store, iid, sid, allow_content=True)['request_id'] for sid in source_ids]
            members = [{'investigation_id': iid}]; draft = {'after_access_id': marker}
            for ids in ([], earlier):
                self.assertFalse(native_request_coverage(store, members, draft, ids)[iid]['complete_for_observed_population'])
            self.assertTrue(native_request_coverage(store, members, draft, later)[iid]['complete_for_observed_population'])

    def test_interrupts_real_process_after_synthetic_native_read_and_preserves_trace(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            code = 'import json,time\nrows=' + repr(native_rows()[:3]) + '\nfor r in rows: print(json.dumps(r),flush=True)\ntime.sleep(30)'
            captured = []
            outcome = run_stage([sys.executable, '-c', code], root, root, {}, 5,
                                interrupt=True, snapshot=lambda: captured.append(True))
            self.assertTrue(outcome['interrupted_after_native_read'])
            self.assertFalse(outcome['timed_out'])
            self.assertEqual(captured, [True])
            self.assertEqual(len((root / 'transcript.jsonl').read_text().splitlines()), 3)

    def test_unresponsive_process_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            outcome = run_stage([sys.executable, '-c', 'import time; time.sleep(30)'], root, root, {}, .2)
            self.assertTrue(outcome['timed_out'])
            self.assertFalse(outcome['interrupted_after_native_read'])
            self.assertIsNotNone(outcome['exit_code'])


if __name__ == '__main__':
    unittest.main()
