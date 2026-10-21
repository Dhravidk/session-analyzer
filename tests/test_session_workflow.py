import copy
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ally_analyzer.engine import analyze_dataset, canonical_report
from ally_analyzer.ingest import import_bundle
from ally_analyzer.mcp import BY_NAME, Protocol, SESSION_TOOLS
from ally_analyzer.service import Service
from ally_analyzer.session_investigation import (accounting, finish_investigation, get_investigation_records,
    get_session_overview, measure_selection, records, save_incident, save_recommendation)
from ally_analyzer.session_patterns import turn_patterns
from ally_analyzer.session_report import export_session_investigation, report_data, render_report
from ally_analyzer.session_scope import (entities, exposure, get_related_evidence, get_run, get_scope,
    read_investigation_batch, read_investigation_evidence, scope_rows, search_investigation_text, start_session_investigation)
from ally_analyzer.session_validation import admit_artifact, get_validation_results, revise_scope, run_fixture_checks
from ally_analyzer.store import SCHEMA, Store
from ally_analyzer.util import AnalyzerError, canonical
from tests.helpers import call, response, result, usage, write_log


def human(i, text="Run one failing test, fix the fixture, then check again.", **kwargs):
    row = response(i, **kwargs)
    row.update(type="user", turnOrigin="human")
    row["message"] = {"role": "user", "content": [{"type": "text", "text": text}]}
    return row


def session_rows():
    return [human(0), call(1, args={"command": "python3 -m unittest"}), result(2, "tool-1", "FAILED (failures=1)", True),
            call(3, name="Edit", args={"file_path": "/fixture/example.py", "old_string": "broken", "new_string": "fixed"}),
            result(4, "tool-3"), call(5, args={"command": "python3 -m unittest"}), result(6, "tool-5", "Ran 1 test. OK."),
            {"type": "system", "subtype": "turn_duration", "uuid": "duration", "sessionId": "session-a", "durationMs": 6000, "timestamp": "2026-09-01T12:00:06.500Z"},
            human(8, "Explain what changed."), response(9, content=[{"type": "text", "text": "The fixture was repaired and the check passed."}])]


class SessionWorkflowTests(unittest.TestCase):
    # Retained v1 payloads must remain exportable with their original policy.
    # The v2 suite exercises the stricter live contract and disclosure gates.
    contract_version = 'single-session-v1'

    def setUp(self):
        contract = patch('ally_analyzer.session_scope.CONTRACT', self.contract_version)
        contract.start()
        self.addCleanup(contract.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "store")
        self.load(session_rows())

    def load(self, rows):
        path = write_log(self.root / ("source-%d.jsonl" % len(list(self.root.glob('source-*')))), rows)
        dataset = import_bundle(self.store, path)
        self.aid = analyze_dataset(self.store, dataset["dataset_id"])["analysis_id"]
        self.run = start_session_investigation(self.store, self.aid, "session-a", "Investigate the captured task")['investigation']
        self.iid = self.run['id']
        self.rows = scope_rows(self.store, self.run)
        self.ids = {json.loads(r['raw']).get('uuid'): r['id'] for r in self.rows}

    def read(self, source_id, **kwargs):
        return read_investigation_evidence(self.store, self.iid, source_id, allow_content=True, **kwargs)

    def incident(self, **changes):
        value = {"title": "Expected failing test followed by repair", "member_event_ids": [self.ids['event-1'], self.ids['event-2']],
                 "tool_ids": ['tool-1'], "task_references": [{"source_id": self.ids['event-0']}], "membership_basis": "Same requested check",
                 "expectedness": "expected", "resolution": "recovered", "diagnosis": "supported", "prior_recognition": "identified_in_session",
                 "remaining_action": "none", "recovery_references": [{"source_id": self.ids['event-6']}], "counterevidence": [],
                 "claims": [{"text": "The requested negative test failed before the repair.", "evidence_class": "recorded_observation",
                             "references": [{"source_id": self.ids['event-2']}], "limitations": [], "support_review": "The result reports a failed test."}],
                 "alternatives": [], "open_questions": [], "provenance": {"model": "synthetic-test", "skill_version": "contract-fixture"}}
        value.update(changes)
        return value

    def proposal(self, **changes):
        incident = save_incident(self.store, self.iid, self.incident())
        ref = {"source_id": self.ids['event-0']}
        review = {k: "Synthetic review of the cited request and recovery." for k in ('intent_and_instructions', 'recovery_and_prior_fix', 'target_applicability', 'alternatives_and_counterevidence', 'claim_support', 'writing_review')}
        review.update(unresolved_material_contradictions=[], references=[ref], provenance={"model": "synthetic-test", "skill_version": "contract-fixture"})
        p = {"title": "A test proposal, not production analysis", "incident_ids": [incident['id']], "claim_ids": incident['claim_ids'],
             "trigger": "When preparing the synthetic fixture", "target_kind": "prompt", "target_references": [ref],
             "change": "Specify the check result to retain.", "justification": "Exercise the contract only.", "tradeoffs": [],
             "verification_plan": {"baseline_or_fixture": "Synthetic request", "intervention": "Add the fixture condition", "conditions": "Same fixture",
                                   "expected_outcome": "Expected result retained", "disconfirming_outcome": "Result still missing", "guardrails": ["Preserve expected negative test"], "required_evidence": ["Captured result"]},
             "contains_executable_snippet": False, "contextual_review": review, "provenance": review['provenance']}
        p.update(changes)
        return p

    def test_session_turn_metrics_do_not_count_tool_results_as_user_turns(self):
        measured = accounting(self.store, self.run)
        self.assertEqual(measured['session']['user_turns']['value'], 2)
        self.assertEqual(measured['session']['llm_calls']['value'], 4)
        self.assertEqual(measured['session']['tool_invocations']['value'], 3)
        self.assertEqual(measured['session']['session_duration_minutes']['value'], 9 / 60)
        first, second = measured['turns']
        self.assertEqual(first['metrics']['llm_calls']['value'], 3)
        self.assertEqual(first['metrics']['prompt_tokens']['value'], 180)
        self.assertEqual(first['metrics']['cached_tokens']['value'], 90)
        self.assertEqual(first['metrics']['cache_creation_tokens']['value'], 60)
        self.assertEqual(first['metrics']['completion_tokens']['value'], 120)
        self.assertEqual(first['metrics']['turn_duration_seconds']['value'], 6)
        self.assertEqual(second['metrics']['observed_turn_span_seconds']['value'], 1)
        self.assertIsNone(second['metrics']['turn_duration_seconds']['value'])
        self.assertEqual(first['metrics']['observed_turn_span_seconds']['value'], 6.5)

    def test_large_turn_navigation_stays_bounded_and_all_members_are_retrievable(self):
        rows = [human(0)]
        for i in range(1, 901, 2):
            rows.extend([call(i), result(i + 1, 'tool-' + str(i))])
        self.load(rows)
        page = get_investigation_records(self.store, self.iid, 'turns')
        self.assertLess(len(canonical(page).encode()), 5000)
        turn = page['items'][0]
        self.assertEqual(turn['metrics']['llm_calls'], 450)
        seen, offset = [], 0
        while True:
            calls = get_investigation_records(self.store, self.iid, 'tools', limit=100, offset=offset, turn_id=turn['id'])
            seen.extend(t['id'] for t in calls['items'])
            if calls['next_offset'] is None: break
            offset = calls['next_offset']
        self.assertEqual(len(set(seen)), 450)
        m = measure_selection(self.store, self.iid, 'tool_invocations', {'turn_id':turn['id'], 'membership_basis':'complete recorded turn'})
        self.assertEqual(m['value'], 450)
        self.assertEqual(m['resolved_identity_counts']['tools'], 450)

    def test_warm_text_search_reuses_projection_without_masking_again(self):
        search_investigation_text(self.store, self.iid, 'fixture', allow_content=True)
        with patch('ally_analyzer.session_scope.trajectory_text', side_effect=AssertionError('Projection rebuilt')):
            result_ = search_investigation_text(self.store, self.iid, 'fixture', allow_content=True)
        self.assertTrue(result_['matches'])

    def test_native_control_messages_do_not_create_turns(self):
        rows = session_rows()
        for i, text in enumerate(("[Request interrupted by user for tool use]", "<local-command-stdout>model set</local-command-stdout>", "<command-name>/model</command-name>"), 20):
            control = human(i, text)
            control.pop('turnOrigin')
            rows.append(control)
        slash = human(23, "<command-name>/team:review</command-name>")
        slash.pop('turnOrigin'); rows.append(slash)
        self.load(rows)
        metric = accounting(self.store, self.run)['session']['user_turns']
        self.assertEqual(metric['value'], 3)
        self.assertEqual(metric['explicit_human_count'], 2)
        self.assertEqual(metric['inferred_origin_count'], 1)

    def test_quantity_lint_flags_unmeasured_calls_but_not_error_codes(self):
        incident = self.incident()
        incident['claims'][0]['text'] = 'The trace contains 999 calls and TS1002.'
        saved = save_incident(self.store, self.iid, incident)
        self.assertEqual(records(self.store, self.iid, 'claim')[0]['quantity_lint']['unmeasured_quantity_candidates'], ['999 calls'])
        self.read(self.ids['event-0'])
        p = self.proposal(claim_ids=saved['claim_ids'], incident_ids=[saved['id']])
        self.assertEqual(save_recommendation(self.store, self.iid, p)['validation']['status'], 'needs_validation')

    def test_unknown_usage_is_null_not_partial_total_or_zero(self):
        rows = session_rows(); rows[1]['message'].pop('usage')
        self.load(rows)
        m = accounting(self.store, self.run)['turns'][0]['metrics']['prompt_tokens']
        self.assertIsNone(m['value']); self.assertEqual(m['known_subtotal'], 120)
        self.assertEqual((m['known'], m['eligible']), (2, 3))

    def test_duplicate_export_deduplicates_but_distinct_retry_remains(self):
        rows = session_rows()
        self.load(rows + copy.deepcopy(rows) + [call(10), result(11, 'tool-10')])
        m = accounting(self.store, self.run)['session']
        self.assertEqual(m['llm_calls']['value'], 5)
        self.assertEqual(m['tool_invocations']['value'], 4)
        self.assertEqual(m['user_turns']['value'], 2)

    def test_pattern_table_denominator_medians_and_failures_are_separate(self):
        m = accounting(self.store, self.run)
        patterns = turn_patterns(m['turns'], entities(self.store, self.run, 'tool'))
        groups = {r['id']: r for r in patterns['rows']}
        self.assertEqual(patterns['denominator'], 2)
        self.assertEqual(groups['edit_check']['median_llm_calls'], 3)
        self.assertEqual(groups['edit_check']['median_tool_batches'], 3)
        self.assertEqual(groups['edit_check']['share'], .5)
        self.assertEqual(groups['edit_check']['recorded_failures'], 1)
        self.assertEqual(groups['llm_only']['share'], .5)
        self.assertAlmostEqual(sum(r['share'] for r in groups.values()), 1)
        self.assertNotIn('waste', canonical(patterns['rows']))

    def test_infrastructure_failure_without_assistant_text_is_retrievable(self):
        self.load([human(0), {'type':'system','uuid':'infra','sessionId':'session-a','subtype':'api_error',
                             'error':{'message':'upstream unavailable','api_key':'private-secret'},'timestamp':'2026-09-01T12:00:01Z'}])
        page = self.read(self.ids['infra'])
        self.assertIn('upstream unavailable', page['text'])
        self.assertIn('api_error', page['text'])
        self.assertNotIn('private-secret', page['text'])
        self.assertEqual(accounting(self.store, self.run)['session']['llm_calls']['value'], 0)

    def test_operator_acceptance_does_not_promote_unvalidated_proposal(self):
        from ally_analyzer.session_validation import review_recommendation
        p = save_recommendation(self.store, self.iid, self.proposal(target_kind='existing_skill'))
        review_recommendation(self.store, self.iid, p['id'], 'tested_beneficial', 'Operator report, no imported execution evidence')
        state = get_validation_results(self.store, self.iid, p['id'])
        self.assertEqual(state['status'], 'needs_evidence')
        self.assertEqual(state['executed_check_count'], 0)
        self.assertEqual(state['operator_reviews'][0]['executor'], 'operator_reported')

    def test_empty_request_and_no_parent_history_remain_visible(self):
        self.load([response(0), human(1)])
        measured = accounting(self.store, self.run)
        self.assertEqual(measured['session']['llm_calls']['value'], 1)
        self.assertEqual(len(measured['attribution_coverage']['responses_without_unambiguous_turn']), 1)
        patterns = turn_patterns(measured['turns'], [])
        self.assertEqual(patterns['rows'][0]['id'], 'no_response')
        self.assertEqual(patterns['rows'][0]['share'], 1)

    def test_recorded_ancestry_overrides_interleaved_timestamp(self):
        rows = [human(0), human(1, "Another task"), response(2)]
        rows[2]['parentUuid'] = 'event-0'
        self.load(rows)
        turns = accounting(self.store, self.run)['turns']
        self.assertEqual([t['metrics']['llm_calls']['value'] for t in turns], [1, 0])

    def test_foreign_session_read_measure_save_and_legacy_escape_are_rejected(self):
        self.load(session_rows() + [human(20, session='foreign'), call(21, session='foreign')])
        with self.store.connect() as db:
            foreign = db.execute("SELECT id FROM events WHERE session_id='foreign' LIMIT 1").fetchone()[0]
        for operation in (lambda: self.read(foreign),
                          lambda: get_related_evidence(self.store, self.iid, foreign),
                          lambda: measure_selection(self.store, self.iid, 'tool_invocations', {'tool_ids': ['tool-21'], 'membership_basis': 'foreign'}),
                          lambda: save_incident(self.store, self.iid, self.incident(member_event_ids=[foreign]))):
            with self.assertRaises(AnalyzerError): operation()
        service = Service(self.store, True); self.addCleanup(service.close)
        service.investigation_id = self.iid
        with self.assertRaises(AnalyzerError): service.call('save_insight', {})
        with self.assertRaises(AnalyzerError): service.call('get_evidence', {'dataset_id': 'x', 'event_id': foreign})
        self.assertGreaterEqual(exposure(self.store, self.iid)['failed_or_denied_requests'], 4)

    def test_missing_child_and_unlinked_child_scope_are_explicit(self):
        rows = [human(0), call(1, name='Agent'), result(2, 'tool-1', meta={'agentId': 'missing-child'}), response(3, agent='unlinked')]
        self.load(rows)
        scope = get_scope(self.store, self.run)
        self.assertEqual(scope['agent_ids'], ['main'])
        self.assertEqual(scope['excluded_unlinked_agents'], ['unlinked'])
        self.assertEqual(scope['capture_gaps']['missing_child_traces'][0]['child_agent_id'], 'missing-child')

    def test_structurally_linked_child_is_counted_once_and_assigned_to_parent(self):
        rows = [human(0), call(1, name='Agent'), result(2, 'tool-1', meta={'agentId': 'child'}), response(3, agent='child')]
        self.load(rows)
        scope = get_scope(self.store, self.run)
        self.assertEqual(scope['agent_ids'], ['child', 'main'])
        m = accounting(self.store, self.run)
        self.assertEqual(m['session']['llm_calls']['value'], 2)
        self.assertEqual(m['turns'][0]['metrics']['llm_calls']['value'], 2)
        self.assertEqual(m['attribution_coverage']['responses_without_unambiguous_turn'], [])

    def test_full_text_pagination_tail_search_unicode_and_exposure_union(self):
        rows = session_rows(); rows[-1]['message']['content'] = [{'type':'text','text': 'a' * 13000 + ' --λ-option=[x.y] recovery'}]
        self.load(rows)
        hit = search_investigation_text(self.store, self.iid, '--λ-option=[x.y]', max_scan=1, allow_content=True)
        self.assertEqual(hit['matches'], []); self.assertIsNotNone(hit['next_scan_offset'])
        hit = search_investigation_text(self.store, self.iid, '--λ-option=[x.y]', scan_offset=hit['next_scan_offset'], allow_content=True)
        self.assertEqual(len(hit['matches']), 1)
        sid = hit['matches'][0]['source_id']
        p1 = self.read(sid, max_chars=8000); self.read(sid, max_chars=8000)
        p2 = self.read(sid, start_char=8000, expected_text_sha256=p1['text_sha256'])
        self.assertIn('recovery', p2['text'])
        delivered = next(s for s in exposure(self.store, self.iid)['sources'] if s['source_id'] == sid)
        self.assertEqual(delivered['delivered_characters'], p1['total_characters'])
        self.assertEqual(delivered['delivered_ranges'], [[0, p1['total_characters']]])
        with self.assertRaises(AnalyzerError): self.read(sid, expected_text_sha256='f' * 64)

    def test_policy_denial_and_omission_are_audited(self):
        with self.assertRaises(AnalyzerError): read_investigation_evidence(self.store, self.iid, self.ids['event-1'])
        self.assertEqual(exposure(self.store, self.iid)['failed_or_denied_requests'], 1)
        rows = session_rows(); rows[1]['message']['content'].append({'type':'thinking','thinking':'Do not disclose'})
        self.load(rows)
        p = self.read(self.ids['event-1'])
        self.assertNotIn('Do not disclose', p['text']); self.assertTrue(p['omitted_categories'])

    def test_batched_reads_are_bounded_continuable_and_all_or_nothing_for_scope(self):
        ids = [self.ids['event-0'], self.ids['event-1']]
        result_ = read_investigation_batch(self.store, self.iid, ids, max_chars_per_source=8, allow_content=True)
        self.assertEqual(len(result_['pages']), 2)
        first = result_['pages'][0]
        rest = self.read(ids[0], start_char=first['next_start_char'], expected_text_sha256=first['text_sha256'])
        self.assertEqual(first['text'] + rest['text'], self.read(ids[0])['text'])
        before = exposure(self.store, self.iid)
        for sources, allow in (([ids[0], 'foreign-source'], True), (ids, False)):
            with self.assertRaises(AnalyzerError):
                read_investigation_batch(self.store, self.iid, sources, allow_content=allow)
        after = exposure(self.store, self.iid)
        self.assertEqual(after['sources'], before['sources'])
        self.assertEqual(after['failed_or_denied_requests'], before['failed_or_denied_requests'] + 2)
        with self.assertRaises(AnalyzerError):
            read_investigation_batch(self.store, self.iid, ids, max_chars_per_source=3001, allow_content=True)

    def test_scope_pins_projection_version_across_parser_upgrade(self):
        rows = session_rows(); rows[-1]['error'] = {'message': 'infrastructure failed'}
        self.load(rows)
        # Construct an old scope through the old version selector, without
        # modifying an existing run or its evidence receipts.
        with patch('ally_analyzer.session_scope.TEXT_VERSION', 'trajectory-text-v1'):
            old = start_session_investigation(self.store, self.aid, 'session-a', 'Old projection')['investigation']
        old_page = read_investigation_evidence(self.store, old['id'], self.ids['event-9'], allow_content=True)
        current_page = self.read(self.ids['event-9'])
        self.assertNotIn('infrastructure failed', old_page['text'])
        self.assertIn('infrastructure failed', current_page['text'])
        self.assertNotEqual(old_page['text_sha256'], current_page['text_sha256'])
        reread = read_investigation_evidence(self.store, old['id'], self.ids['event-9'],
                                            expected_text_sha256=old_page['text_sha256'], allow_content=True)
        self.assertEqual(reread['text'], old_page['text'])
        self.assertEqual(reread['text_version'], 'trajectory-text-v1')

    def test_graph_cycle_is_bounded_and_call_result_link_is_locatable(self):
        rows = session_rows(); rows[1]['parentUuid'] = 'event-2'; rows[2]['parentUuid'] = 'event-1'
        self.load(rows)
        graph = get_related_evidence(self.store, self.iid, 'tool:tool-1', depth=6, limit=2)
        self.assertLessEqual(len(graph['edges']), 2)
        self.assertIsNotNone(graph['next_offset'])
        self.assertTrue(any(d['code'] == 'parent_cycle' for d in get_scope(self.store, self.run)['capture_gaps']['graph_diagnostics']))
        all_edges = get_related_evidence(self.store, self.iid, 'tool:tool-1', depth=2, limit=100)['edges']
        self.assertTrue(any(e['relation'] == 'has_result' and e['target'] == 'event:' + self.ids['event-2'] for e in all_edges))

    def test_selected_quantities_and_opportunity_population_cannot_be_invented(self):
        measurement = measure_selection(self.store, self.iid, 'tool_invocations', {'tool_ids':['tool-1','tool-3','tool-5'], 'membership_basis':'captured tools'})
        self.assertEqual(measurement['value'], 3)
        incident = self.incident()
        incident['claims'][0].update(evidence_class='calculated', measurement_id=measurement['id'], expected_value=999)
        with self.assertRaises(AnalyzerError): save_incident(self.store, self.iid, incident)
        self.assertEqual(records(self.store, self.iid, 'claim'), [])
        incident['claims'][0]['expected_value'] = 3
        save_incident(self.store, self.iid, incident)
        with self.assertRaises(AnalyzerError):
            measure_selection(self.store, self.iid, 'occurrence_rate', {'tool_ids':['tool-1'], 'membership_basis':'selected'}, opportunity_tool_ids=['tool-3'])
        rate = measure_selection(self.store, self.iid, 'occurrence_rate', {'tool_ids':['tool-1'], 'membership_basis':'selected'}, opportunity_tool_ids=['tool-1','tool-3'])
        self.assertEqual(rate['value'], .5)

    def test_overlapping_measurements_are_nonadditive_and_union_deduplicates(self):
        first = measure_selection(self.store, self.iid, 'tool_invocations', {'tool_ids':['tool-1','tool-3'], 'membership_basis':'first'})
        second = measure_selection(self.store, self.iid, 'tool_invocations', {'tool_ids':['tool-3','tool-5'], 'membership_basis':'second'})
        union = measure_selection(self.store, self.iid, 'tool_invocations', {'tool_ids':['tool-1','tool-3','tool-5'], 'membership_basis':'union'})
        self.assertTrue(first['non_additive'] and second['non_additive'])
        self.assertEqual(union['value'], 3)
        with self.assertRaises(AnalyzerError): measure_selection(self.store, self.iid, 'tool_invocations', {'tool_ids':['tool-1','tool-1'], 'membership_basis':'duplicate'})

    def test_no_action_insufficient_and_partial_are_distinct_frozen_states(self):
        save_incident(self.store, self.iid, self.incident())
        finish_investigation(self.store, self.iid, 'completed', 'no_action_supported', 'Expected test and completed recovery.', 'Inspected the task and result.', [], 'Inquiry complete')
        with self.assertRaises(AnalyzerError): save_incident(self.store, self.iid, self.incident())
        self.load([human(0), response(1)])
        with self.assertRaises(AnalyzerError): finish_investigation(self.store, self.iid, 'partial', 'insufficient_evidence', 'Incomplete.', 'Read request.', [], 'Budget limit')
        finish_investigation(self.store, self.iid, 'partial', 'insufficient_evidence', 'The outcome is not captured.', 'Read request.', ['What was the final outcome?'], 'Budget limit')
        self.assertEqual(get_run(self.store, self.iid)['run_status'], 'partial')

    def test_range_citations_are_checked_against_immutable_masked_projection(self):
        page = self.read(self.ids['event-2'])
        incident = self.incident()
        ref = {'source_id': self.ids['event-2'], 'text_sha256': page['text_sha256'], 'start_char': 0, 'end_char': len(page['text'])}
        incident['claims'][0]['references'] = [ref]
        save_incident(self.store, self.iid, incident)
        ref['end_char'] += 1
        with self.assertRaises(AnalyzerError): save_incident(self.store, self.iid, incident)

    def test_uninspected_target_cannot_be_ready_and_scope_revision_keeps_history(self):
        p = self.proposal(target_kind='existing_skill')
        saved = save_recommendation(self.store, self.iid, p)
        self.assertEqual(saved['validation']['status'], 'needs_evidence')
        file = self.root / 'skill.md'; file.write_text('Read the current input before editing.')
        art = admit_artifact(self.store, file, 'Fixture skill', 'current', 'complete')
        with self.assertRaises(AnalyzerError): self.read(art['id'])
        revised = revise_scope(self.store, self.iid, [art['id']])['investigation']
        self.assertNotEqual(revised['scope_id'], self.run['scope_id'])
        self.assertEqual(get_run(self.store, self.iid)['scope_id'], self.run['scope_id'])
        self.assertEqual(records(self.store, revised['id'], 'recommendation'), [])

    def test_newer_snapshot_in_scope_prevents_obsolete_target_readiness(self):
        path = self.root / 'skill-target.md'; path.write_text('Original procedure')
        old = admit_artifact(self.store, path, 'Skill', 'current', 'complete')['id']
        path.write_text('Procedure with the fix already included')
        new = admit_artifact(self.store, path, 'Skill', 'current', 'complete')['id']
        self.run = revise_scope(self.store, self.iid, [old,new])['investigation']; self.iid = self.run['id']
        self.read(old)
        p = self.proposal(target_kind='existing_skill', target_snapshot_id=old, target_references=[{'source_id':old}])
        self.assertEqual(save_recommendation(self.store, self.iid, p)['validation']['status'], 'needs_evidence')

    def test_prompt_readiness_requires_reading_the_original_request_and_model_review(self):
        proposal = self.proposal()
        first = save_recommendation(self.store, self.iid, proposal)
        self.assertEqual(first['validation']['status'], 'needs_evidence')
        self.read(self.ids['event-0'])
        status = get_validation_results(self.store, self.iid, first['id'])
        self.assertEqual(status['status'], 'ready_for_review')
        self.assertEqual(status['executed_check_count'], 0)
        self.assertEqual(next(c for c in status['checks'] if c['check_type']=='contextual_review')['executor'], 'caller_model_review')
        proposal['contextual_review']['unresolved_material_contradictions'] = ['The request already contains the alleged missing instruction.']
        proposal['revision_of'] = first['id']
        revised = save_recommendation(self.store, self.iid, proposal)
        self.assertEqual(revised['validation']['status'], 'needs_validation')
        self.assertEqual(get_validation_results(self.store, self.iid, first['id'])['superseded_by'], [revised['id']])

    def test_machine_attestations_cannot_be_submitted_by_the_model(self):
        proposal = self.proposal()
        proposal['machine_checks'] = [{'status':'passed'}]
        with self.assertRaises(AnalyzerError): save_recommendation(self.store, self.iid, proposal)
        names = {t['name'] for t in SESSION_TOOLS}
        self.assertNotIn('run_fixture_checks', names); self.assertNotIn('admit_artifact', names)
        service = Service(self.store); self.addCleanup(service.close)
        with self.assertRaises(AnalyzerError): service.call('record_check', {'status':'passed'})

    def executable_proposal(self, candidate_text):
        target = self.root / 'target.json'; target.write_text('{"matcher":"Bash"}')
        candidate = self.root / 'candidate.json'; candidate.write_text(candidate_text)
        target_id = admit_artifact(self.store, target, 'Existing hook', 'current', 'complete')['id']
        candidate_id = admit_artifact(self.store, candidate, 'Proposed hook', 'proposed', 'complete')['id']
        self.run = revise_scope(self.store, self.iid, [target_id,candidate_id])['investigation']; self.iid = self.run['id']
        self.read(target_id)
        p = self.proposal(target_kind='hook', target_snapshot_id=target_id, candidate_snapshot_id=candidate_id,
                          target_references=[{'source_id':target_id}], contains_executable_snippet=True)
        return save_recommendation(self.store, self.iid, p)

    def fixture(self):
        directory = self.root / 'fixture'; directory.mkdir()
        (directory / 'check.py').write_text('''import json,re,sys
p=json.load(open(sys.argv[1]))
mode=sys.argv[2]
assert set(p)=={'matcher'} and isinstance(p['matcher'], str)
matcher=re.compile(p['matcher'])
def decision(tool, command):
    return 'deny' if matcher.fullmatch(tool) and command.startswith('git commit') else 'allow'
if mode=='target_contract':
    assert matcher.fullmatch('Bash') and not matcher.fullmatch('BashPrefix')
elif mode=='positive_behavior':
    assert decision('Bash', 'git commit -m example')=='deny'
elif mode=='negative_behavior':
    assert decision('Read', 'git commit -m example')=='allow'
    assert decision('Bash', 'git status')=='allow'
print('fixture checked')
''')
        checks = [{'check_type': name, 'argv':[sys.executable, 'check.py', '{candidate}', name], 'expected_exit':0,
                   'stdout_contains':'fixture checked'} for name in ('syntax_or_schema','target_contract','positive_behavior','negative_behavior')]
        plan = self.root / 'plan.json'; plan.write_text(json.dumps({'version':'fixture-v2','environment':'Synthetic tool-dispatch fixture; not native Claude hook schema validation','candidate_filename':'candidate.json','checks':checks}))
        return directory, plan

    def test_wrong_hook_fixture_fails_and_cannot_be_hidden_by_readiness(self):
        p = self.executable_proposal('{"matcher":"Bash(git commit*)"}')
        self.assertEqual(p['validation']['status'], 'needs_validation')
        directory, plan = self.fixture()
        result_ = run_fixture_checks(self.store, self.iid, p['id'], directory, plan)
        status = {c['check_type']:c['status'] for c in result_['executions']}
        self.assertEqual(status, {'syntax_or_schema':'passed', 'target_contract':'failed', 'positive_behavior':'failed', 'negative_behavior':'passed'})
        self.assertEqual(result_['validation']['status'], 'needs_validation')
        self.assertEqual(result_['validation']['passed_execution_count'], 2)

    def test_negative_hook_fixture_rejects_overbroad_matcher(self):
        p = self.executable_proposal('{"matcher":".*"}')
        directory, plan = self.fixture()
        result_ = run_fixture_checks(self.store, self.iid, p['id'], directory, plan)
        status = {c['check_type']:c['status'] for c in result_['executions']}
        self.assertEqual(status['positive_behavior'], 'passed')
        self.assertEqual(status['negative_behavior'], 'failed')
        self.assertEqual(result_['validation']['status'], 'needs_validation')

    def test_unavailable_fixture_runtime_is_not_an_executed_or_passed_check(self):
        p = self.executable_proposal('{"matcher":"Bash"}')
        directory, plan = self.fixture()
        value = json.loads(plan.read_text())
        for check in value['checks']: check['argv'][0] = str(self.root / 'missing-runtime')
        plan.write_text(json.dumps(value))
        result_ = run_fixture_checks(self.store, self.iid, p['id'], directory, plan)
        self.assertTrue(all(c['status']=='unavailable' and c['exit_code'] is None for c in result_['executions']))
        self.assertEqual(result_['validation']['executed_check_count'], 0)
        self.assertEqual(result_['validation']['passed_execution_count'], 0)
        self.assertEqual(result_['validation']['status'], 'needs_validation')

    def test_gate_that_checks_only_one_error_code_fails_behavior_fixture(self):
        script = "import sys\nfailed='TS1005' in sys.stdin.read()\nprint('FAIL' if failed else 'PASS')\nsys.exit(1 if failed else 0)\n"
        proposal = self.executable_proposal(script)
        directory = self.root / 'gate-fixture'; directory.mkdir()
        (directory / 'syntax.py').write_text('import ast,sys\nast.parse(open(sys.argv[1]).read())\n')
        checks = [
            {'check_type':'syntax_or_schema','argv':[sys.executable,'syntax.py','{candidate}'],'expected_exit':0},
            {'check_type':'positive_behavior','argv':[sys.executable,'{candidate}'],'stdin':'page.ts(1,1): error TS1002: Unterminated string literal.','expected_exit':1,'stdout_contains':'FAIL'},
            {'check_type':'negative_behavior','argv':[sys.executable,'{candidate}'],'stdin':'No errors.','expected_exit':0,'stdout_contains':'PASS'}]
        plan = self.root / 'gate-plan.json'
        plan.write_text(json.dumps({'version':'gate-fixture-v1','environment':'Synthetic syntax gate; requires rejection of every error code','candidate_filename':'gate.py','checks':checks}))
        result_ = run_fixture_checks(self.store, self.iid, proposal['id'], directory, plan)
        self.assertEqual({c['check_type']:c['status'] for c in result_['executions']},
                         {'syntax_or_schema':'passed','positive_behavior':'failed','negative_behavior':'passed'})
        self.assertEqual(result_['validation']['status'], 'needs_validation')

    def test_bound_fixture_execution_checks_invalidate_on_proposal_revision(self):
        p = self.executable_proposal('{"matcher":"Bash"}')
        directory, plan = self.fixture()
        result_ = run_fixture_checks(self.store, self.iid, p['id'], directory, plan)
        self.assertEqual(result_['validation']['status'], 'ready_for_review')
        revised = copy.deepcopy(p['recommendation']); revised['change'] = 'Different proposed behavior'; revised['revision_of'] = p['id']
        new = save_recommendation(self.store, self.iid, revised)
        self.assertEqual(new['validation']['executed_check_count'], 0)
        self.assertEqual(new['validation']['status'], 'needs_validation')

    def test_exact_authored_text_is_preserved_and_html_escaped(self):
        incident = self.incident(title='<script>alert("x")</script>')
        saved = save_incident(self.store, self.iid, incident)
        self.assertEqual(saved['incident'], incident)
        data = report_data(self.store, self.iid)
        rendered = render_report(data)
        self.assertNotIn('<script>alert', rendered)
        self.assertIn('&lt;script&gt;alert', rendered)
        self.assertEqual(data['incidents'][0]['incident'], incident)
        self.assertIn('Turn patterns', rendered); self.assertIn('Input total', rendered)
        dest = self.root / 'report.html'
        export_session_investigation(self.store, self.iid, dest)
        with self.assertRaises(AnalyzerError): export_session_investigation(self.store, self.iid, dest)

    def test_no_network_or_canonical_mutation_in_scoped_workflow(self):
        before = canonical(canonical_report(self.store, self.aid))
        with patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')):
            get_session_overview(self.store, self.iid)
            self.read(self.ids['event-0'])
            save_incident(self.store, self.iid, self.incident())
            export_session_investigation(self.store, self.iid, self.root / 'offline.json', 'json')
        self.assertEqual(canonical(canonical_report(self.store, self.aid)), before)

    def test_scoped_stdio_and_cli_expose_same_metrics_and_enforce_scope(self):
        root = Path(__file__).resolve().parent.parent
        env = dict(os.environ, ALLY_ANALYZER_INVESTIGATION_ID=self.iid,
                   ALLY_ANALYZER_SESSION_ONLY='1', ALLY_ANALYZER_ALLOW_CONTENT='1')
        messages = [
            {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'session-test','version':'1'}}},
            {'jsonrpc':'2.0','method':'notifications/initialized'},
            {'jsonrpc':'2.0','id':2,'method':'tools/list'},
            {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'get_session_overview','arguments':{'investigation_id':self.iid}}},
            {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'read_investigation_batch','arguments':{'investigation_id':self.iid,'source_ids':[self.ids['event-0']]}}},
            {'jsonrpc':'2.0','id':5,'method':'tools/call','params':{'name':'list_analyses','arguments':{}}}]
        process = subprocess.run([sys.executable,str(root/'bin'/'ally-session'),'--data-dir',str(self.store.root),'mcp'],
                                 input=''.join(canonical(m)+'\n' for m in messages),capture_output=True,text=True,env=env,cwd=self.root,timeout=15)
        self.assertEqual(process.returncode, 0, process.stderr)
        responses = {r['id']:r for r in map(json.loads, process.stdout.splitlines())}
        names = {t['name'] for t in responses[2]['result']['tools']}
        self.assertIn('read_investigation_batch', names)
        self.assertNotIn('read_trajectory_event', names); self.assertNotIn('start_session_investigation', names)
        self.assertEqual(responses[4]['result']['structuredContent']['pages'][0]['text'], human(0)['message']['content'][0]['text'])
        self.assertTrue(responses[5]['result']['isError'])
        cli = subprocess.run([sys.executable,'-m','ally_analyzer','--data-dir',str(self.store.root),'session-overview',self.iid],
                             cwd=root,capture_output=True,text=True,timeout=15)
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(json.loads(cli.stdout)['session_metrics'], responses[3]['result']['structuredContent']['session_metrics'])

    def test_legacy_database_backup_and_transactional_rollback(self):
        root = self.root / 'migration'; root.mkdir()
        path = root / 'analysis.sqlite3'
        with sqlite3.connect(path) as db:
            db.executescript(SCHEMA); db.execute('PRAGMA user_version=1')
            db.execute("INSERT INTO insights VALUES ('old','analysis','{}','now')")
        with patch('ally_analyzer.session_schema.SCHEMA', 'CREATE TABLE temporary_migration(x); INVALID SQL;'):
            with self.assertRaises(sqlite3.OperationalError): Store(root)
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 1)
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='temporary_migration'").fetchone())
            self.assertEqual(db.execute('SELECT id FROM insights').fetchone()[0], 'old')
        self.assertTrue((root / 'analysis.pre-v3.sqlite3').exists())
        Store(root)
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 3)
            self.assertEqual(db.execute('SELECT id FROM insights').fetchone()[0], 'old')


if __name__ == '__main__':
    unittest.main()
