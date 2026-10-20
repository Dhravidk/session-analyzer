"""Developer reply facts and the retained accounting behind the compact opening."""
import copy
import os
import unittest
from unittest.mock import patch

from ally_analyzer.engine import analyze_dataset
from ally_analyzer.guidance import get_session_guide
from ally_analyzer.service import Service
from ally_analyzer.session_investigation import get_session_overview, query_measurement
from ally_analyzer.session_readout import developer_readout
from ally_analyzer.session_readout import prepare_session_reply
from ally_analyzer.session_report import agent_cost_html, report_data
from ally_analyzer.session_resources import get_context_timeline
from ally_analyzer.session_scope import start_session_investigation
from ally_analyzer.session_investigation import records
from ally_analyzer.util import AnalyzerError
from tests import test_session_workflow as workflow
from tests.helpers import call, response, result, usage
from tests.test_session_cost import PRICES, snapshot
from tests.test_session_workflow import human


class DeveloperReadoutTests(unittest.TestCase):
    contract_version = 'single-session-v2'
    setUp = workflow.SessionWorkflowTests.setUp
    load = workflow.SessionWorkflowTests.load

    def test_opening_has_four_counts_with_subsets_and_matching_scope(self):
        self.load([human(0), response(1), snapshot(2, 12.34)])
        overview = get_session_overview(self.store, self.iid)
        text = overview['session_readout']['opening']
        self.assertEqual(text, 'You spent approximately $12.34 (60 input tokens, including 30 cached input tokens; 40 output tokens, including 12 reasoning tokens) on this session.')
        self.assertEqual(overview['session_readout']['cost_kind'], 'recorded_snapshot')
        self.assertIn('final session cost is unverified', ' '.join(overview['session_readout']['qualifications']))
        self.assertEqual(overview['session_metrics']['thinking_tokens']['value'], 12)
        data = report_data(self.store, self.iid)
        before = copy.deepcopy(data)
        self.assertEqual(data['session_readout'], overview['session_readout'])
        self.assertIn(text, agent_cost_html(data))
        self.assertEqual(data, before)

    def test_missing_reasoning_is_unavailable_while_output_stays_inclusive(self):
        self.load([human(0), response(1), response(2, u=usage(thinking=None)), snapshot(3, 4)])
        readout = get_session_overview(self.store, self.iid)['session_readout']
        self.assertIn('80 output tokens; reasoning tokens unavailable', readout['opening'])
        self.assertIsNone(readout['usage']['reasoning_output_tokens']['value'])
        self.assertEqual(readout['usage']['reasoning_output_tokens']['known_subtotal'], 12)

    def test_empty_usage_is_not_fabricated_zero(self):
        readout = developer_readout(None, {})
        self.assertTrue(readout['opening'].startswith('Session cost is unavailable'))
        self.assertIn('input tokens unavailable', readout['opening'])
        self.assertIn('reasoning tokens unavailable', readout['opening'])
        self.assertNotIn('$0.00', readout['opening'])

    def test_partial_pricing_cannot_become_spent_total(self):
        prices = copy.deepcopy(PRICES)
        prices['rates']['test-model']['input_per_million'] = '1000000'
        # One response uses an unmatched model; retain its usage, not a fabricated price.
        rows = [human(0), response(1), response(2)]
        rows[2]['message']['model'] = 'unpriced-model'
        self.load(rows); dataset = self.store.analysis(self.aid)['dataset_id']
        aid = analyze_dataset(self.store, dataset, prices=prices)['analysis_id']
        run = start_session_investigation(self.store, aid, 'session-a', 'Synthetic partial pricing')['investigation']
        readout = get_session_overview(self.store, run['id'])['session_readout']
        self.assertEqual(readout['cost_kind'], 'priced_subtotal')
        self.assertTrue(readout['opening'].startswith('Priced usage subtotal: $10.00'))
        self.assertIn('full session cost is unknown', readout['opening'])
        self.assertIn('120 input tokens', readout['opening'])

    def test_main_and_captured_children_are_counted_once_not_mixed_with_analyzer(self):
        self.load([human(0), call(1, name='Agent'), result(2, 'tool-1', meta={'agentId': 'child'}),
                   response(3, agent='child'), response(4, agent='unlinked'), snapshot(5, 7)])
        readout = get_session_overview(self.store, self.iid)['session_readout']
        self.assertEqual(readout['usage']['input_tokens']['value'], 120)
        self.assertEqual(readout['usage']['reasoning_output_tokens']['value'], 24)
        self.assertEqual(readout['usage']['output_tokens']['value'], 80)
        self.assertIn('captured children', readout['population'])

    def test_compactions_tools_and_registered_cache_queries_still_work(self):
        boundary = {'type': 'system', 'subtype': 'compact_boundary', 'uuid': 'compact', 'sessionId': 'session-a',
                    'timestamp': '2026-09-01T12:00:03Z',
                    'compactMetadata': {'trigger': 'manual', 'preTokens': 200, 'postTokens': 50, 'durationMs': 100}}
        self.load([human(0), call(1), result(2, 'tool-1', error=True), boundary, response(4), snapshot(5, 3)])
        overview = get_session_overview(self.store, self.iid)
        self.assertEqual(overview['session_metrics']['tool_invocations']['value'], 1)
        share = query_measurement(self.store, self.iid, formula='cache_read_share', selection={'all_scoped': True, 'membership_basis': 'All captured synthetic responses'})
        self.assertEqual(share['value'], .5)
        timeline = get_context_timeline(self.store, self.iid)
        self.assertEqual(timeline['coverage']['recorded_compaction_count'], 1)
        data = report_data(self.store, self.iid)
        self.assertTrue(data['resource_views']['main']['context'])

    def test_runtime_delivers_the_new_reply_contract_without_removing_tools(self):
        with patch.dict(os.environ, {'ALLY_ANALYZER_INVESTIGATION_ID': self.iid}, clear=True):
            service = Service(self.store); self.addCleanup(service.close)
        result = service.call('get_session_overview', {'investigation_id': self.iid})
        self.assertIn('session_readout', result)
        writing = next(g['instructions'] for g in result['session_guides'] if g['skill'].endswith(':write-report'))
        self.assertEqual(writing, get_session_guide('write-report')['instructions'])
        self.assertIn('session_readout.opening', writing)
        self.assertIn('Caching and compaction detail is on request', writing)
        self.assertIn('not permission to skip the work', writing)
        self.assertFalse(service.allow_content)

    def test_reply_preflight_adds_factual_opening_without_editing_authored_body(self):
        body = 'Follow the existing approval rule.\n\nFinish the draft before seeking implementation approval.\n'
        before = records(self.store, self.iid, 'incident')
        result = prepare_session_reply(self.store, self.iid, body)
        self.assertEqual(result['status'], 'ready')
        self.assertTrue(result['reply'].startswith(result['session_readout']['opening']))
        self.assertTrue(result['reply'].endswith(body))
        self.assertEqual(records(self.store, self.iid, 'incident'), before)

    def test_unrequested_resource_detail_is_returned_for_revision_not_rewritten(self):
        body = 'Use one-hour prompt caching. The context compaction event may have lost an instruction.'
        result = prepare_session_reply(self.store, self.iid, body)
        self.assertEqual(result['status'], 'needs_revision')
        self.assertNotIn('reply', result)
        self.assertEqual({i['code'] for i in result['issues']}, {'unrequested_cache_detail', 'unrequested_compaction_detail'})
        self.assertIn('one-hour', body)

    def test_requested_topics_require_a_current_request_and_do_not_opt_in_other_topics(self):
        with self.assertRaises(AnalyzerError):
            prepare_session_reply(self.store, self.iid, 'Cache-read tokens were recorded.', ['cache'])
        cache_only = prepare_session_reply(self.store, self.iid, 'The context compaction event is recorded.',
            ['cache'], 'Explain cached input usage.')
        self.assertEqual(cache_only['issues'][0]['code'], 'unrequested_compaction_detail')
        both = prepare_session_reply(self.store, self.iid, 'Cache-read tokens and the context compaction event are recorded.',
            ['cache', 'compaction'], 'Explain the caching and compaction events.')
        self.assertEqual(both['status'], 'ready')

    def test_task_specific_application_cache_is_not_misclassified_as_resource_tuning(self):
        result = prepare_session_reply(self.store, self.iid, 'Fix Redis cache invalidation in cache.py, then rerun the application test.')
        self.assertEqual(result['status'], 'ready')

    def test_reply_preflight_uses_existing_bound_scope_and_content_policy(self):
        with patch.dict(os.environ, {'ALLY_ANALYZER_INVESTIGATION_ID': self.iid}, clear=True):
            service = Service(self.store); self.addCleanup(service.close)
        result = service.call('prepare_session_reply', {'investigation_id': self.iid, 'body': 'The requested check passed.'})
        self.assertEqual(result['status'], 'ready')
        self.assertFalse(service.allow_content)
        with self.assertRaises(AnalyzerError):
            service.call('prepare_session_reply', {'investigation_id': 'unrelated', 'body': 'Another session.'})
