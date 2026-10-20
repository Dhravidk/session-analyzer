"""Source cost coverage and native cumulative snapshots, using synthetic logs only."""
import copy
from decimal import Decimal
import unittest

from ally_analyzer.engine import analyze_dataset
from ally_analyzer.session_cost import cost_readout, latest_snapshot, source_session_cost
from ally_analyzer.session_investigation import get_session_overview
from ally_analyzer.session_markdown import render_markdown
from ally_analyzer.session_report import agent_cost_html, render_report, report_data
from ally_analyzer.session_scope import start_session_investigation
from tests.helpers import call, response, result, usage
from tests import test_session_workflow as workflow
from tests.test_session_workflow import human


PRICES = {'version': 'synthetic-cost-v1', 'provider': 'test-provider', 'effective_date': '2026-01-01',
          'rates': {'test-model': {'input_per_million': '1', 'output_per_million': '2',
                    'cache_read_per_million': '0.1', 'cache_write_5m_per_million': '1.25',
                    'cache_write_1h_per_million': '2', 'service_tier': 'standard', 'speed': 'standard'}}}


def snapshot(index, value, **extra):
    # Native cost-state records often have no timestamp. Imported source order matters.
    return {'uuid': 'cost-' + str(index), 'sessionId': 'session-a', 'type': 'cost-state',
            'totalCostUSD': value, 'startTime': 1000, 'modelUsage': {}, **extra}


class SessionCostTests(unittest.TestCase):
    contract_version = 'single-session-v2'
    setUp = workflow.SessionWorkflowTests.setUp
    load = workflow.SessionWorkflowTests.load

    def cost(self, rows, prices=None):
        self.load(rows)
        if prices:
            dataset = self.store.analysis(self.aid)['dataset_id']
            self.aid = analyze_dataset(self.store, dataset, prices=prices)['analysis_id']
            self.run = start_session_investigation(self.store, self.aid, 'session-a', 'Synthetic cost check')['investigation']
            self.iid = self.run['id']
        return source_session_cost(self.store, self.run)

    def test_unknown_cost_is_not_zero_and_is_first_in_both_exports(self):
        data = report_data(self.store, self.iid)
        original = copy.deepcopy(data)
        readout = cost_readout(data['source_cost'])
        self.assertEqual(readout['value'], 'Unavailable')
        output = render_report(data)
        self.assertLess(output.index('id="agent-cost"'), output.index('<h1>'))
        self.assertIn('Session cost is unavailable', agent_cost_html(data))
        self.assertNotIn('$0.00', agent_cost_html(data))
        self.assertIn('A compliance verdict is not established.', output)
        markdown = render_markdown(data)
        self.assertTrue(markdown.startswith('Session cost is unavailable'))
        self.assertLess(markdown.index('Instruction and task compliance'), markdown.index('Main\\-agent metrics'))
        self.assertEqual(data, original)

    def test_pinned_rates_count_cache_ttl_and_thinking_once(self):
        cost = self.cost([human(0), response(1)], PRICES)
        self.assertEqual(cost['priced_usage']['value_usd'], '0.000118')
        self.assertTrue(cost['priced_usage']['complete_for_captured_responses'])
        self.assertEqual(cost_readout(cost)['value'], '<$0.01')
        self.assertEqual(cost['priced_usage']['price_book']['version'], PRICES['version'])
        self.assertEqual(get_session_overview(self.store, self.iid)['source_cost']['priced_usage']['value_usd'], '0.000118')
        parts = cost['priced_usage']['components']
        self.assertEqual(Decimal(parts['input']['value_usd']), Decimal('0.000038'))
        self.assertEqual(Decimal(parts['cached_input']['value_usd']), Decimal('0.000003'))
        self.assertEqual(Decimal(parts['output']['value_usd']), Decimal('0.000080'))
        self.assertEqual(Decimal(parts['reasoning_output']['value_usd']), Decimal('0.000024'))
        # Only the two inclusive categories add to the source total.
        self.assertEqual(sum(Decimal(parts[k]['value_usd']) for k in ('input', 'output')),
                         Decimal(cost['priced_usage']['value_usd']))

    def test_unknown_reasoning_does_not_remove_known_output_cost(self):
        cost = self.cost([human(0), response(1, u=usage(thinking=None))], PRICES)
        parts = cost['priced_usage']['components']
        self.assertEqual(Decimal(parts['output']['value_usd']), Decimal('0.000080'))
        self.assertIsNone(parts['reasoning_output']['value_usd'])
        self.assertIsNone(parts['reasoning_output']['known_subtotal_usd'])
        self.assertEqual(cost['priced_usage']['value_usd'], '0.000118')

    def test_mixed_cache_ttls_are_priced_without_double_counting(self):
        row = response(1)
        row['message']['usage']['cache_creation'] = {'ephemeral_5m_input_tokens': 5, 'ephemeral_1h_input_tokens': 15}
        cost = self.cost([human(0), row], PRICES)
        self.assertEqual(Decimal(cost['priced_usage']['components']['input']['value_usd']), Decimal('0.00004925'))
        self.assertEqual(Decimal(cost['priced_usage']['value_usd']), Decimal('0.00012925'))

    def test_partial_pricing_is_a_subtotal_even_with_a_host_estimate(self):
        missing = response(2)
        missing['message'].pop('usage')
        cost = self.cost([human(0), response(1), missing, snapshot(3, 42)], PRICES)
        self.assertEqual(cost['priced_usage']['known_responses'], 1)
        self.assertEqual(cost['priced_usage']['eligible_responses'], 2)
        self.assertFalse(cost['priced_usage']['complete_for_captured_responses'])
        self.assertIn('subtotal', cost_readout(cost)['label'])
        self.assertIn('full cost is unknown', cost_readout(cost)['basis'])
        self.assertEqual(cost['recorded_snapshot']['value_usd'], '42')
        self.assertEqual(cost['priced_usage']['value_usd'], '0.000118')
        self.assertIsNone(cost['priced_usage']['components']['input']['value_usd'])
        self.assertEqual(cost['priced_usage']['components']['input']['known_subtotal_usd'], '0.000038')

    def test_streaming_fragments_are_priced_as_one_response(self):
        cost = self.cost([human(0), response(1, mid='streamed', request='stream-request', block=0),
                          response(2, mid='streamed', request='stream-request', block=1)], PRICES)
        self.assertEqual(cost['priced_usage']['known_responses'], 1)
        self.assertEqual(cost['priced_usage']['value_usd'], '0.000118')
        self.assertEqual(len(cost['priced_usage']['source_ids']), 2)

    def test_latest_untimestamped_snapshot_is_not_sum_or_max_across_processes(self):
        cost = self.cost([human(0), snapshot(1, 50), response(2), snapshot(3, 60),
                          snapshot(4, 3.25, startTime=2000), response(5)])
        saved = cost['recorded_snapshot']
        self.assertEqual(saved['value_usd'], '3.25')
        self.assertEqual(saved['distinct_main_snapshots'], 3)
        self.assertEqual(saved['later_main_responses'], 1)
        self.assertEqual(saved['response_order_coverage'], {'comparable': 2, 'main_responses': 2})
        self.assertIn('Captured order in source member', saved['order_basis'])
        self.assertIn('not a final session total', ' '.join(cost['limitations']))
        self.assertEqual(cost_readout(cost)['value'], '$3.25')
        data = report_data(self.store, self.iid)
        source = data['sources'][saved['source_ids'][0]]
        self.assertEqual(source['captured_cost_fields'], {'totalCostUSD': 3.25, 'startTime': 2000})
        self.assertIn('Recorded host cost snapshot', agent_cost_html(data))
        self.assertNotIn('Explanation not saved', agent_cost_html(data))

    def test_child_snapshots_and_analyzer_cost_do_not_inflate_source_cost(self):
        self.cost([human(0), call(1, name='Agent'), result(2, 'tool-1', meta={'agentId': 'child'}),
                   response(3, agent='child'), snapshot(4, 999, agentId='child'), snapshot(5, 4)])
        data = report_data(self.store, self.iid)
        data['investigation']['analyzer_usage'] = {'total_cost_usd': 777}
        self.assertEqual(data['source_cost']['recorded_snapshot']['value_usd'], '4')
        output = agent_cost_html(data)
        self.assertIn('$4.00', output)
        self.assertNotIn('777', output)
        self.assertNotIn('999', output)

    def test_uncaptured_children_qualify_a_complete_priced_capture(self):
        cost = self.cost([human(0), call(1, name='Agent'), result(2, 'tool-1', meta={'agentId': 'missing'})], PRICES)
        self.assertTrue(cost['priced_usage']['complete_for_captured_responses'])
        self.assertIn('full task cost', ' '.join(cost['limitations']))

    def test_unlinked_child_usage_is_excluded_and_zero_cost_can_be_known(self):
        cost = self.cost([human(0), response(1, u=usage(input=0, write=0, read=0, output=0, thinking=0)),
                          response(2, agent='unlinked')], PRICES)
        self.assertEqual(Decimal(cost['priced_usage']['value_usd']), 0)
        self.assertEqual(cost['priced_usage']['eligible_responses'], 1)
        self.assertEqual(cost_readout(cost)['value'], '$0.00')

    def test_invalid_snapshot_is_not_coerced_and_source_estimate_stays_available(self):
        cost = self.cost([human(0), snapshot(1, 8), snapshot(2, True), snapshot(3, -10), snapshot(4, 'unknown')])
        self.assertEqual(cost['recorded_snapshot']['value_usd'], '8')
        self.assertIn('3 invalid', ' '.join(cost['limitations']))

    def test_snapshot_order_ambiguity_is_preserved(self):
        first = {'id': 'a', 'timestamp': None}
        second = {'id': 'b', 'timestamp': None}
        self.assertEqual(latest_snapshot([(first, 10), (second, 20)], {'a': {'one': 1}, 'b': {'two': 1}}), (None, None))
        self.assertEqual(latest_snapshot([(first, 10), (second, 20)],
                         {'a': {'one': 1, 'two': 2}, 'b': {'one': 2, 'two': 1}}), (None, None))

    def test_retained_report_without_new_cost_field_remains_renderable(self):
        data = report_data(self.store, self.iid)
        data.pop('source_cost')
        self.assertIn('Session cost is unavailable', agent_cost_html(data))
        self.assertIn('Session cost is unavailable', render_markdown(data))
