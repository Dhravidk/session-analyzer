"""Conversational reads must work after finalization without editing judgments."""
import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ally_analyzer.engine import analyze_dataset, canonical_report
from ally_analyzer.ingest import import_bundle
from ally_analyzer.service import Service
from ally_analyzer.session_investigation import measure_selection, query_measurement
from ally_analyzer.session_queries import inspect_response_accounting, list_session_investigations
from ally_analyzer.session_scope import entities, get_run, start_session_investigation
from ally_analyzer.store import Store
from ally_analyzer.util import AnalyzerError, canonical
from tests.helpers import call, response, result, usage, write_log


class SessionQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'store')
        rows = [response(0, mid='stream', request='req-stream', block=0, u=usage(output=10, thinking=3)),
                response(1, mid='stream', request='req-stream', block=1, u=usage(output=40)),
                response(2)]
        dataset = import_bundle(self.store, write_log(self.root / 'synthetic.jsonl', rows))
        self.aid = analyze_dataset(self.store, dataset['dataset_id'])['analysis_id']
        self.run = self.start()
        self.iid = self.run['id']

    def start(self, aid=None, session='session-a'):
        return start_session_investigation(self.store, aid or self.aid, session, 'Synthetic conversational regression')['investigation']

    def freeze(self, run=None, status='completed'):
        frozen = dict(run or self.run, run_status=status, conclusion='no_action_supported',
                      summary='Synthetic saved judgment. Do not edit.', created_at='2026-09-02T00:00:00Z')
        with self.store.connect() as db:
            db.execute('UPDATE session_runs SET payload=?,created_at=? WHERE id=?', (canonical(frozen), frozen['created_at'], frozen['id']))
        return frozen

    def records(self):
        with self.store.connect() as db:
            return [tuple(r) for r in db.execute('SELECT * FROM investigation_records ORDER BY id')]

    def test_frozen_queries_reuse_same_calculations_without_changing_saved_analysis(self):
        selections = [('cache_read_share', {'all_scoped': True, 'membership_basis': 'All captured responses in the selected synthetic scope'}), ('cache_creation_tokens', {'all_scoped': True, 'membership_basis': 'All captured responses in the selected synthetic scope'}),
                      ('completion_tokens', {'all_scoped': True, 'membership_basis': 'All captured responses in the selected synthetic scope'})]
        saved = [measure_selection(self.store, self.iid, formula, selection) for formula, selection in selections]
        frozen = self.freeze(); records = self.records()
        original = canonical(canonical_report(self.store, self.aid))
        for (formula, selection), measurement in zip(selections, saved):
            answer = query_measurement(self.store, self.iid, formula, selection)
            for key, value in measurement.items():
                if key != 'id': self.assertEqual(answer[key], value, key)
            self.assertFalse(answer['saved_as_claim_evidence'])
            self.assertNotIn('id', answer)
            self.assertEqual(answer['scope_id'], self.run['scope_id'])
        self.assertEqual(self.records(), records)
        self.assertEqual(get_run(self.store, self.iid), frozen)
        self.assertEqual(canonical(canonical_report(self.store, self.aid)), original)
        with self.assertRaisesRegex(AnalyzerError, 'frozen'):
            measure_selection(self.store, self.iid, 'cache_read_share', {'all_scoped': True, 'membership_basis': 'All captured responses in the selected synthetic scope'})

    def test_readonly_query_rejects_foreign_duplicate_and_mixed_populations(self):
        rid = entities(self.store, self.run, 'response')[0]['id']
        for selection in ({'response_ids': ['foreign'], 'membership_basis':'Synthetic foreign identity'}, {'response_ids': [rid, rid], 'membership_basis':'Synthetic duplicate identities'}, {'all_scoped': True, 'response_ids': [rid], 'membership_basis':'Synthetic mixed selection'}):
            with self.assertRaises(AnalyzerError): query_measurement(self.store, self.iid, 'cache_read_share', selection)

    def test_source_accounting_exposes_both_stream_frames_not_two_responses(self):
        stream = next(r for r in entities(self.store, self.run, 'response') if r['message_id'] == 'stream')
        first = inspect_response_accounting(self.store, self.iid, stream['id'], limit=1)
        second = inspect_response_accounting(self.store, self.iid, stream['id'], limit=1, offset=first['next_offset'])
        self.assertEqual(first['total'], 2)
        self.assertIsNone(second['next_offset'])
        frames = first['frames'] + second['frames']
        self.assertEqual({f['captured_usage_fields']['output_tokens']['value'] for f in frames}, {10, 40})
        self.assertEqual(first['reconciled']['tokens']['output_tokens'], 40)
        self.assertEqual(first['reconciled']['usage_status'], 'reconciled_stream_update')
        self.assertTrue(all(f['source']['source_refs'] and f['source']['payload_sha256'] for f in frames))
        self.assertEqual(query_measurement(self.store, self.iid, 'response_count', {'all_scoped': True, 'membership_basis': 'All captured responses in the selected synthetic scope'})['value'], 2)
        with self.assertRaises(AnalyzerError): inspect_response_accounting(self.store, self.iid, 'foreign')

    def test_missing_and_invalid_fields_stay_unknown_without_disclosing_payloads(self):
        row = response(5)
        u = row['message']['usage']; del u['cache_read_input_tokens']
        u['cache_creation_input_tokens'] = 'secret arbitrary text'
        u['output_tokens_details']['thinking_tokens'] = None
        u['private_extra'] = {'text': 'secret arbitrary text'}
        row['message']['content'] = [{'type':'thinking', 'thinking':'do not disclose thinking'}, {'type':'text','text':'do not disclose prose'}]
        dataset = import_bundle(self.store, write_log(self.root / 'malformed.jsonl', [row]))
        aid = analyze_dataset(self.store, dataset['dataset_id'])['analysis_id']
        run = self.start(aid); rid = entities(self.store, run, 'response')[0]['id']
        answer = inspect_response_accounting(self.store, run['id'], rid)
        fields = answer['frames'][0]['captured_usage_fields']
        self.assertEqual(fields['cache_read_input_tokens']['state'], 'absent')
        self.assertEqual(fields['cache_creation_input_tokens'], {'state':'invalid','value':None,'value_type':'str'})
        self.assertEqual(fields['output_tokens_details.thinking_tokens']['state'], 'null')
        self.assertNotIn('secret arbitrary text', canonical(answer))
        self.assertNotIn('do not disclose', canonical(answer))
        query = query_measurement(self.store, run['id'], 'cache_read_share', {'all_scoped': True, 'membership_basis': 'All captured responses in the selected synthetic scope'})
        self.assertIsNone(query['value']); self.assertIsNone(query['known_population_ratio'])
        self.assertEqual(query['known'], 0); self.assertEqual(query['eligible'], 1)

    def test_conflicting_frames_are_not_certified_by_inspection(self):
        rows = [response(6, mid='conflict', request='same', block=0), response(7, mid='conflict', request='same', block=0, u=usage(read=900))]
        dataset = import_bundle(self.store, write_log(self.root / 'conflict.jsonl', rows))
        run = self.start(analyze_dataset(self.store, dataset['dataset_id'])['analysis_id'])
        rid = entities(self.store, run, 'response')[0]['id']
        answer = inspect_response_accounting(self.store, run['id'], rid)
        self.assertEqual(answer['reconciled']['usage_status'], 'conflict')
        self.assertIsNone(answer['reconciled']['tokens']['total_input_tokens'])
        self.assertTrue(answer['reconciled']['warnings'])
        self.assertEqual({f['captured_usage_fields']['cache_read_input_tokens']['value'] for f in answer['frames']}, {30, 900})

    def test_agent_filter_keeps_children_and_shared_identities_out_of_main_turn_totals(self):
        request = {'type':'user', 'turnOrigin':'human', 'uuid':'request', 'sessionId':'session-a',
                   'timestamp':'2026-09-01T12:00:00Z', 'message':{'role':'user','content':'Synthetic child accounting exercise.'}}
        rows = [request, call(1, name='Agent'), result(2, 'tool-1', meta={'agentId':'child'}),
                response(3, agent='child', u=usage(write=200)), response(4),
                response(5, mid='shared', request='shared'), response(6, agent='child', mid='shared', request='shared'),
                call(7, name='Agent'), result(8, 'tool-7', meta={'agentId':'missing-child'})]
        dataset = import_bundle(self.store, write_log(self.root/'children.jsonl', rows))
        run = self.start(analyze_dataset(self.store, dataset['dataset_id'])['analysis_id'])
        base = {'all_scoped':True, 'membership_basis':'Synthetic complete captured scope'}
        combined = query_measurement(self.store, run['id'], 'cache_creation_tokens', base)
        main = query_measurement(self.store, run['id'], 'cache_creation_tokens', dict(base, agent_id='main'))
        self.assertEqual(combined['value'], 280)
        self.assertEqual(main['value'], 60)
        self.assertEqual(len(main['agent_selection']['shared_response_ids_excluded']), 1)
        from ally_analyzer.session_investigation import accounting
        turn = accounting(self.store, run)['turns'][0]['id']
        own_turn = query_measurement(self.store, run['id'], 'cache_creation_tokens',
                                    {'turn_id':turn, 'agent_id':'main', 'membership_basis':'Synthetic main turn only'})
        self.assertEqual(own_turn['value'], 60)
        with self.assertRaisesRegex(AnalyzerError, 'unknown, not zero'):
            query_measurement(self.store, run['id'], 'cache_creation_tokens', dict(base, agent_id='missing-child'))
        with self.assertRaisesRegex(AnalyzerError, 'outside'):
            query_measurement(self.store, run['id'], 'cache_creation_tokens', dict(base, agent_id='foreign'))
        with self.assertRaisesRegex(AnalyzerError, 'requires'):
            query_measurement(self.store, run['id'], 'cache_creation_tokens', {'agent_id':'main', 'membership_basis':'Invalid selector'})

    def test_saved_discovery_is_filtered_paged_and_does_not_infer_freshness(self):
        self.freeze()
        other = self.start(); self.freeze(other, status='partial')
        # Explicit creation order, not title, status or file mtime.
        with self.store.connect() as db:
            value = get_run(self.store, other['id']); value['created_at'] = '2026-09-03T00:00:00Z'
            db.execute('UPDATE session_runs SET payload=?,created_at=? WHERE id=?', (canonical(value), value['created_at'], other['id']))
        page = list_session_investigations(self.store, self.aid, 'session-a', limit=1)
        self.assertEqual(page['items'][0]['id'], other['id'])
        self.assertEqual(page['items'][0]['run_status'], 'partial')
        self.assertEqual(page['freshness'], 'not_compared_to_live_source')
        self.assertNotIn('Synthetic saved judgment', canonical(page))
        self.assertEqual(list_session_investigations(self.store, self.aid, limit=1, offset=page['next_offset'])['items'][0]['id'], self.iid)
        self.assertEqual(list_session_investigations(self.store, self.aid, session_id='different')['total'], 0)
        with self.assertRaises(AnalyzerError): list_session_investigations(self.store, 'unknown')

    def test_discovery_cannot_bypass_bound_scope_and_metadata_needs_no_content_permission(self):
        with patch.dict(os.environ, {}, clear=True):
            service = Service(self.store); self.addCleanup(service.close)
        self.assertEqual(service.call('list_session_investigations', {'analysis_id': self.aid})['total'], 1)
        self.assertIsNone(service.investigation_id)
        rid = entities(self.store, self.run, 'response')[0]['id']
        service.call('inspect_response_accounting', {'investigation_id': self.iid, 'response_id': rid})
        self.assertEqual(service.investigation_id, self.iid)
        with self.assertRaises(AnalyzerError): service.call('list_session_investigations', {'analysis_id': self.aid})
        with self.assertRaises(AnalyzerError): service.call('query_measurement', {'investigation_id': self.start()['id'], 'formula':'cache_read_share', 'selection':{'all_scoped':True}})
        self.assertFalse(service.allow_content)

    def test_guide_is_exact_packaged_skill_available_when_bound_without_changing_policy(self):
        with patch.dict(os.environ, {'ALLY_ANALYZER_INVESTIGATION_ID': self.iid}, clear=True):
            service = Service(self.store); self.addCleanup(service.close)
        for skill in ('explain', 'write-report'):
            guide = service.call('get_session_guide', {'skill': skill})
            path = Path(__file__).resolve().parent.parent / 'skills' / skill / 'SKILL.md'
            self.assertEqual(guide['instructions'], path.read_text())
        self.assertEqual(service.investigation_id, self.iid)
        self.assertFalse(service.allow_content)
        with self.assertRaises(AnalyzerError): service.call('get_session_guide', {'skill':'../../private'})
        with self.assertRaises(AnalyzerError): service.call('get_session_guide', {'path':'/private'})

    def test_definitions_deliver_both_skills_once_and_allow_reload(self):
        service = Service(self.store); self.addCleanup(service.close)
        first = service.call('get_definitions', {})
        self.assertEqual({g['skill'] for g in first['session_guides']},
                         {'ally-session-analyzer:explain', 'ally-session-analyzer:write-report'})
        self.assertEqual(first['guide_errors'], [])
        self.assertEqual(service.call('get_definitions', {})['session_guides'], [])
        self.assertEqual(service.call('get_session_guide', {'skill': 'explain'}),
                         next(g for g in first['session_guides'] if g['skill'].endswith(':explain')))
        self.assertFalse(service.allow_content)
        with patch('ally_analyzer.guidance.get_session_guide', side_effect=AnalyzerError('Missing bundled skill')):
            another = Service(self.store); self.addCleanup(another.close)
            result = another.call('get_definitions', {})
            self.assertEqual(len(result['guide_errors']), 2)
            self.assertEqual(result['session_guides'], [])
            self.assertTrue(result['definitions'])

    def test_first_data_query_delivers_guides_even_if_host_skips_definitions(self):
        service = Service(self.store); self.addCleanup(service.close)
        result = service.call('query_measurement', {'investigation_id':self.iid, 'formula':'cache_read_share',
                              'selection':{'all_scoped':True, 'membership_basis':'Synthetic first query'}})
        self.assertEqual(result['value'], .5)
        self.assertEqual({g['skill'] for g in result['session_guides']},
                         {'ally-session-analyzer:explain', 'ally-session-analyzer:write-report'})
        self.assertEqual(service.call('get_definitions', {})['session_guides'], [])

    def test_oversized_result_does_not_mark_undelivered_guides_as_delivered(self):
        from ally_analyzer.mcp import Protocol, MAX_RESULT_BYTES
        service = Service(self.store); self.addCleanup(service.close)
        protocol = Protocol(service)
        protocol.handle({'jsonrpc':'2.0', 'id':1, 'method':'initialize', 'params':{'protocolVersion':'2025-06-18'}})
        protocol.handle({'jsonrpc':'2.0', 'method':'notifications/initialized'})
        with patch.object(service, '_call', return_value={'large':'x' * MAX_RESULT_BYTES}):
            result = protocol.handle({'jsonrpc':'2.0','id':2,'method':'tools/call',
                                      'params':{'name':'get_summary','arguments':{'analysis_id':self.aid}}})
        self.assertTrue(result['result']['isError'])
        self.assertEqual(service.delivered_guides, set())
        self.assertEqual(len(service.call('get_definitions', {})['session_guides']), 2)

    def test_cli_discovers_and_queries_frozen_scope_without_a_report_server(self):
        self.freeze()
        plugin = Path(__file__).resolve().parent.parent
        base = [sys.executable, str(plugin/'scripts/ally-session.py'), '--data-dir', str(self.store.root)]
        discovered = subprocess.run(base + ['session-investigations', self.aid, '--session-id', 'session-a'],
                                    cwd=self.root, capture_output=True, text=True, timeout=15)
        self.assertEqual(discovered.returncode, 0, discovered.stderr)
        self.assertEqual(json.loads(discovered.stdout)['items'][0]['id'], self.iid)
        arguments = self.root/'query.json'
        arguments.write_text(json.dumps({'investigation_id':self.iid, 'formula':'cache_read_share',
                            'selection':{'all_scoped':True, 'membership_basis':'Synthetic CLI regression scope'}}))
        queried = subprocess.run(base + ['session-call','query_measurement',str(arguments)],
                                 cwd=self.root, capture_output=True, text=True, timeout=15)
        self.assertEqual(queried.returncode, 0, queried.stderr)
        answer = json.loads(queried.stdout)
        self.assertEqual(answer['value'], .5)
        self.assertFalse(answer['saved_as_claim_evidence'])


if __name__ == '__main__': unittest.main()
