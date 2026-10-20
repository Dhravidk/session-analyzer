"""Synthetic native-host streams test reviewer attribution, not model quality."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.test_claude_developer_reply import native_review_activity


class NativeReplyAuditTests(unittest.TestCase):
    def test_parent_self_submission_is_not_an_independent_child_review(self):
        self.check(child=False, expected=False)

    def test_child_submission_and_fresh_reads_are_linked_to_exact_native_launch(self):
        self.check(child=True, expected=True)

    def check(self, child, expected):
        linkage = {'parent_tool_use_id':'synthetic-launch', 'agent_id':'synthetic-child'} if child else {}
        def tool(cid, name, data, **meta):
            return {'type':'assistant','message':{'content':[{'type':'tool_use','id':cid,'name':name,'input':data}]}, **meta}
        def result(cid, data, **meta):
            return {'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':cid,
                     'content':[{'type':'text','text':json.dumps(data)}]}]}, **meta}
        rows = [tool('synthetic-launch','Agent',{'subagent_type':'ally-session-analyzer:source-review'}),
                tool('synthetic-read','scoped__read_investigation_batch',{}, **linkage),
                result('synthetic-read',{'pages':[{'request_id':'synthetic-access','text_sha256':'synthetic-sha','text':'Synthetic source.'}]}, **linkage),
                tool('synthetic-submit','scoped__submit_session_reply_review',{}, **linkage),
                result('synthetic-submit',{'status':'ready','review_id':'synthetic-review','reply':'Synthetic final.'}, **linkage),
                {'type':'result','result':'Synthetic final.'}]
        accepted = [{'id':'synthetic-review', 'reply':'Synthetic final.',
                     'submission':{'source_checks':[{'access_id':'synthetic-access'}]}}]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'synthetic-stream.jsonl'
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            activity=native_review_activity(path, accepted, 'Synthetic final.')
        self.assertEqual(activity['native_launch_count'], 1)
        self.assertEqual(activity['final_matches_native_review'], expected)
        self.assertEqual(activity['decisive_checks_read_by_native_reviewer'], expected)
