"""Automatic pricing over labelled synthetic sessions; no Claude or network."""
import copy
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch

from ally_analyzer.engine import analyze_dataset, canonical_report, validate_prices
from ally_analyzer.pricing import resolve_prices
from ally_analyzer.service import Service
from ally_analyzer.session_investigation import get_session_overview
from ally_analyzer.session_report import agent_cost_html, report_data
from ally_analyzer.session_scope import get_run
from ally_analyzer.util import AnalyzerError, canonical, strict_json
from tests import test_session_workflow as workflow
from tests.helpers import call, response, result, usage
from tests.test_session_cost import PRICES, snapshot
from tests.test_developer_readout import ASSESSMENTS, COMPLIANCE
from tests.test_session_workflow import human


def model_response(index, model='claude-opus-5-5', **kwargs):
    row = response(index, **kwargs)
    row['message']['model'] = model
    return row


class AutomaticPricingTests(unittest.TestCase):
    contract_version = 'single-session-v2'
    setUp = workflow.SessionWorkflowTests.setUp
    load = workflow.SessionWorkflowTests.load

    def overview(self, rows):
        self.load(rows)
        return get_session_overview(self.store, self.iid)

    def test_default_analysis_pins_verified_rates_and_four_dollar_components(self):
        with patch('socket.create_connection', side_effect=AssertionError('No network')), \
             patch('subprocess.Popen', side_effect=AssertionError('No model subprocess')):
            data = self.overview([human(0), model_response(1, u=usage(input=100000, write=200000,
                read=300000, output=40000, thinking=10000))])
        # Opus 5.5: $4 input, $5 writes, $.20 reads, $20 output / million.
        opening = data['session_readout']['opening']
        self.assertEqual(opening, 'Estimated session cost: $2.26.')
        self.assertIn('600,000 input tokens / $1.46, including 300,000 cached input tokens / $0.06', data['session_readout']['token_summary'])
        self.assertIn('40,000 output tokens / $0.80, including 10,000 reasoning tokens / $0.20', data['session_readout']['token_summary'])
        cfg = self.store.analysis(self.aid)['configuration']
        self.assertEqual(cfg['price_book_source']['kind'], 'bundled_verified')
        self.assertEqual(cfg['price_book_source']['verified_on'], '2026-10-20')
        self.assertEqual(len(cfg['price_book_source']['catalog_sha256']), 64)
        self.assertEqual(data['session_readout']['qualifications'], [])
        self.assertIn('not a subscription charge', data['session_readout']['cost_details_on_request'][0])

    def test_known_models_and_stream_updates_are_priced_once(self):
        rows = [human(0), model_response(1, mid='synthetic-stream', request='synthetic-request', block=0),
                model_response(2, mid='synthetic-stream', request='synthetic-request', block=1),
                model_response(3, 'claude-opus-5')]
        cost = self.overview(rows)['source_cost']['priced_usage']
        # 10*4+20*5+30*.2+40*20=946; legacy Opus5=1190, divided by 1M.
        self.assertEqual(Decimal(cost['value_usd']), Decimal('0.002136'))
        self.assertEqual(cost['known_responses'], 2)

    def test_scoped_tools_return_priced_opening_through_simulated_review_without_claude(self):
        self.overview([human(0),model_response(1)])
        before=canonical(canonical_report(self.store,self.aid))
        service=Service(self.store,allow_content=False);self.addCleanup(service.close)
        with patch('socket.create_connection',side_effect=AssertionError('No network')), \
             patch('subprocess.Popen',side_effect=AssertionError('No Claude')):
            draft=service.call('prepare_session_reply',{'investigation_id':self.iid,'body':ASSESSMENTS,'compliance':COMPLIANCE})
            self.assertEqual(draft['status'],'review_required')
            reviewed=service.call('submit_session_reply_review',{'investigation_id':self.iid,'draft_id':draft['draft_id'],
                'body':ASSESSMENTS,'compliance':COMPLIANCE,'notes':'Synthetic simulated metadata-only review; no model was invoked.','source_checks':[]})
            ready=service.call('get_reviewed_session_reply',{'investigation_id':self.iid,'draft_id':draft['draft_id']})
        self.assertEqual(ready['reply'],reviewed['reply'])
        self.assertTrue(ready['reply'].startswith('Estimated session cost:'))
        self.assertEqual(ready['reply'].splitlines()[0].count('cost unavailable'),0)
        self.assertTrue(ready['reply'].endswith(ASSESSMENTS))
        self.assertEqual(canonical(canonical_report(self.store,self.aid)),before)

    def test_threshold_uses_each_prompt_including_cached_tokens(self):
        low = model_response(1, 'claude-haiku-5-5', u=usage(input=1, write=0, read=99999, output=10, thinking=2))
        high = model_response(2, 'claude-haiku-5-5', u=usage(input=1, write=0, read=100000, output=10, thinking=2))
        cost = self.overview([human(0), low, high])['source_cost']['priced_usage']
        # <=100000: $.10/$.50/$.01. >100000: $.50/$2.50/$.05.
        expected = (Decimal('.1') + 99999*Decimal('.01') + 10*Decimal('.5')
                    + Decimal('.5') + 100000*Decimal('.05') + 10*Decimal('2.5'))/1000000
        self.assertEqual(Decimal(cost['value_usd']), expected)

    def test_fast_and_us_multipliers_stack_and_unknown_modes_remain_unknown(self):
        row = model_response(1); row['message']['usage'].update(speed='fast', inference_geo='us')
        cost = self.overview([human(0), row])['source_cost']['priced_usage']
        self.assertEqual(Decimal(cost['value_usd']), Decimal('.000946')*2*Decimal('1.1'))
        for model, key, value in [('claude-opus-5-5', 'service_tier', 'priority'),
                                  ('claude-sonnet-5-5', 'speed', 'fast'),
                                  ('claude-opus-5-5', 'inference_geo', 'unrecognized')]:
            with self.subTest(model=model, key=key):
                row=model_response(1, model);row['message']['usage'][key]=value
                data=self.overview([human(0),row])
                self.assertIsNone(data['source_cost']['priced_usage']['value_usd'])
                self.assertTrue(data['session_readout']['opening'].startswith('Session cost is unavailable'))

    def test_unknown_models_are_not_guessed_and_partial_prices_stay_subtotals(self):
        data=self.overview([human(0), model_response(1), model_response(2,'claude-opus-5-5-unknown')])
        self.assertTrue(data['session_readout']['opening'].startswith('Priced usage subtotal:'))
        self.assertIn('full session cost is unknown', data['session_readout']['opening'])
        self.assertIsNone(data['session_readout']['usage']['input_tokens']['cost_usd'])

    def test_recorded_host_total_is_kept_separate_from_token_estimate(self):
        data=self.overview([human(0),model_response(1),snapshot(2,9.29)])
        self.assertEqual(Decimal(data['source_cost']['priced_usage']['value_usd']),Decimal('.000946'))
        self.assertEqual(data['source_cost']['recorded_snapshot']['value_usd'],'9.29')
        self.assertIn('separate host estimate is $9.29', ' '.join(data['session_readout']['cost_details_on_request']))
        self.assertEqual(data['session_readout']['qualifications'], [])
        self.assertNotIn('$9.29',data['session_readout']['opening'])

    def test_default_reviewed_reply_omits_routine_notes_but_followup_tools_retain_them(self):
        self.overview([human(0), model_response(1, u=usage(input=100000, write=200000,
            read=300000, output=40000, thinking=10000)), snapshot(2, 9.29)])
        before=canonical(canonical_report(self.store,self.aid))
        service=Service(self.store,allow_content=False);self.addCleanup(service.close)
        with patch('socket.create_connection',side_effect=AssertionError('No network')), \
             patch('subprocess.Popen',side_effect=AssertionError('No Claude')):
            draft=service.call('prepare_session_reply',{'investigation_id':self.iid,'body':ASSESSMENTS,'compliance':COMPLIANCE})
            ready=service.call('submit_session_reply_review',{'investigation_id':self.iid,'draft_id':draft['draft_id'],
                'body':ASSESSMENTS,'compliance':COMPLIANCE,'notes':'Synthetic offline review, no model.','source_checks':[]})
            self.assertEqual(ready['status'],'ready')
            self.assertEqual(ready['reply'],'Estimated session cost: $2.26.\n\n'+ASSESSMENTS)
            followup=service.call('get_session_overview',{'investigation_id':self.iid})
        detail=followup['session_readout']
        self.assertIn('600,000 input tokens / $1.46',detail['token_summary'])
        self.assertEqual(detail['usage']['cached_input_tokens']['cost_usd'],'0.06')
        self.assertEqual(detail['usage']['reasoning_output_tokens']['value'],10000)
        self.assertTrue(any('verified 2026-10-20' in note for note in detail['cost_details_on_request']))
        self.assertTrue(any('separate host estimate is $9.29' in note for note in detail['cost_details_on_request']))
        self.assertEqual(followup['source_cost']['recorded_snapshot']['value_usd'],'9.29')
        self.assertEqual(canonical(canonical_report(self.store,self.aid)),before)

    def test_operator_rate_card_takes_precedence_without_automatic_merge(self):
        prices=copy.deepcopy(PRICES);prices['rates']['claude-opus-5-5']=prices['rates'].pop('test-model')
        self.load([human(0),model_response(1)])
        aid=analyze_dataset(self.store,self.store.analysis(self.aid)['dataset_id'],prices=prices)['analysis_id']
        report=canonical_report(self.store,aid)
        self.assertEqual(report['summary']['metrics']['cost_estimate_usd']['value'],'0.000118')
        self.assertEqual(report['summary']['configuration']['price_book_source']['kind'],'explicit')
        self.assertEqual(prices['version'],'synthetic-cost-v1')

    def test_pinned_rates_do_not_depend_on_later_catalog_availability(self):
        self.overview([human(0),model_response(1)])
        before=canonical(canonical_report(self.store,self.aid))
        with patch('ally_analyzer.pricing.resolve_prices',side_effect=AssertionError('Pinned card must win')):
            data=get_session_overview(self.store,self.iid)
        self.assertEqual(Decimal(data['source_cost']['priced_usage']['value_usd']),Decimal('.000946'))
        self.assertEqual(canonical(canonical_report(self.store,self.aid)),before)

    def test_old_unpriced_scope_can_read_new_prices_without_mutation_or_geo_loss(self):
        row=model_response(1);row['message']['usage']['inference_geo']='us'
        self.overview([human(0),row])
        cfg=self.store.analysis(self.aid)['configuration'];cfg['price_book']=None;cfg.pop('price_book_source')
        with self.store.connect() as db:
            db.execute('UPDATE analyses SET configuration=? WHERE id=?',(canonical(cfg),self.aid))
            for saved in db.execute("SELECT id,payload FROM scope_entities WHERE scope_id=? AND kind='response'",(self.run['scope_id'],)).fetchall():
                value=strict_json(saved['payload']);value.pop('inference_geo',None)
                db.execute("UPDATE scope_entities SET payload=? WHERE scope_id=? AND kind='response' AND id=?",(canonical(value),self.run['scope_id'],saved['id']))
        before=canonical(canonical_report(self.store,self.aid))
        data=get_session_overview(self.store,self.iid)
        self.assertEqual(Decimal(data['source_cost']['priced_usage']['value_usd']),Decimal('.000946')*Decimal('1.1'))
        self.assertIsNone(self.store.analysis(self.aid)['configuration']['price_book'])
        self.assertEqual(canonical(canonical_report(self.store,self.aid)),before)

    def test_source_and_linked_children_exclude_analyzer_usage(self):
        parent=call(1,name='Agent');parent['message']['model']='claude-opus-5-5'
        rows=[human(0),parent,result(2,'tool-1',meta={'agentId':'synthetic-child'}),
              model_response(3,agent='synthetic-child'),model_response(4,agent='synthetic-unlinked')]
        data=self.overview(rows)
        self.assertEqual(data['source_cost']['priced_usage']['eligible_responses'],2)
        self.assertEqual(Decimal(data['source_cost']['priced_usage']['value_usd']),Decimal('.001892'))
        # Persist the actual managed-run telemetry shape, including its review
        # phase, before recalculating the source-session opening.
        run=get_run(self.store,self.iid)
        run['analyzer_usage']={'status':'host_reported','cost_usd':12345,
            'usage':[{'phase':'review','usage':{'input_tokens':987654321,'output_tokens':1234567}}],
            'source_session_usage_included':False}
        with self.store.connect() as db:
            db.execute('UPDATE session_runs SET payload=? WHERE id=?',(canonical(run),self.iid))
        recalculated=get_session_overview(self.store,self.iid)
        self.assertEqual(recalculated['session_readout'],data['session_readout'])
        output=report_data(self.store,self.iid)
        original=copy.deepcopy(output['session_readout'])
        rendered=agent_cost_html(output)
        self.assertNotIn('12345',rendered);self.assertNotIn('987654321',rendered)
        self.assertEqual(output['session_readout'],original)

    def test_catalog_failures_do_not_silently_fabricate_prices(self):
        with patch.object(Path,'read_text',side_effect=OSError('Synthetic missing resource')):
            with self.assertRaisesRegex(AnalyzerError,'Bundled verified pricing is unavailable'):
                resolve_prices()
        book,_=resolve_prices();book['billing_rules']['fast_multipliers']['claude-opus-5-5']='NaN'
        with self.assertRaises(AnalyzerError):validate_prices(book)
        book,_=resolve_prices();book['currency']='EUR'
        with self.assertRaises(AnalyzerError):validate_prices(book)
        first,_=resolve_prices();first['rates'].clear()
        again,_=resolve_prices();self.assertIn('claude-opus-5-5',again['rates'])
