"""v2 adversarial closure, instruction readiness and document data regressions."""
import copy
import json
import re
import unittest
from unittest.mock import patch
from pathlib import Path

from ally_analyzer.session_diagnostics import get_diagnostic_status, save_inquiry, read_turn_evidence, coverage_assertions
from ally_analyzer.session_investigation import accounting, finish_investigation, save_incident, save_recommendation
from ally_analyzer.session_report import report_data, render_report, export_session_investigation, turn_incidents, pattern_failure_entries
from ally_analyzer.session_scope import exposure, get_run, start_session_investigation
from ally_analyzer.session_validation import admit_artifact, get_validation_results
from ally_analyzer.util import AnalyzerError
from tests import test_session_workflow as legacy
from tests.test_session_workflow import human, session_rows


class DiagnosticTests(unittest.TestCase):
    contract_version='single-session-v2'
    setUp=legacy.SessionWorkflowTests.setUp
    load=legacy.SessionWorkflowTests.load
    read=legacy.SessionWorkflowTests.read
    proposal=legacy.SessionWorkflowTests.proposal

    def incident(self, **changes):
        i=legacy.SessionWorkflowTests.incident(self)
        for c in i['claims']: c['subject']='recorded_action'
        i.update(changes)
        return i

    def read_all(self):
        for sid in self.ids.values(): self.read(sid, max_chars=12000)

    def inquiry(self, **changes):
        q={'question':'Did the requested repair pass its final check?', 'kind':'task_outcome',
           'why_it_matters':'Distinguish expected failure from an unresolved task.', 'status':'answered',
           'answer':'The final result records a passed check.', 'references':[{'source_id':self.ids['event-6']}],
           'next_source_ids':[], 'missing_evidence':[]}
        q.update(changes)
        return q

    def finish(self, **changes):
        p={'run_status':'completed','conclusion':'no_action_supported','summary':'The expected failure was repaired.',
           'coverage_explanation':'Synthetic captured parent only.', 'unresolved_questions':[], 'stop_reason':'Requested check inspected.',
           'title':'Repair a synthetic fixture', 'synopsis':{'text':'The user requested a failing test, fixture repair and another check. The trace records the repair and a passing result.',
                   'references':[{'source_id':self.ids['event-0']},{'source_id':self.ids['event-6']}],'limitations':[]},
           'observed_outcome':{'text':'The final check passed.','evidence_class':'recorded_observation',
                   'references':[{'source_id':self.ids['event-6']}],'limitations':[]},'stop_basis':'inquiry_answered'}
        p.update(changes)
        return finish_investigation(self.store,self.iid,**p)

    def instruction(self, kind='claude_md', operation='replace', replacement='Run `python -m unittest`.\n'):
        target=self.root/'CLAUDE.md'
        original='Run `python check.py`.\n'
        target.write_text('---\nname: check-fixture\n---\n'+original)
        aid=admit_artifact(self.store,target,'Fixture instructions','current','complete','fixture-v1')['id']
        self.run=start_session_investigation(self.store,self.aid,'session-a','Test exact instruction edit',artifact_ids=[aid])['investigation']
        self.iid=self.run['id'];self.read_all();self.read(aid)
        edit={'operation':operation,'target_path':str(target),'scope':'Synthetic fixture directory only',
              'location':'The sole check command line','original_text':original,'replacement_text':replacement}
        if operation=='invoke':
            edit.pop('original_text');edit.pop('replacement_text');edit['invocation']='/check-fixture'
        if operation=='create': edit.pop('original_text')
        ir={'existing_requirement':'incorrect','assessment':'The captured fixture instruction names the old command.',
            'scope_references':[{'source_id':aid},{'source_id':self.ids['event-0']}], 'inspected_instruction_ids':[aid],
            'inventory_status':'complete_for_declared_scope', 'overlap_assessment':'Only the admitted synthetic instruction exists in this fixture scope.',
            'reuse_assessment':'Replace its command, preserving the existing procedure.',
            'alternative_interventions':'No executable implementation change is represented by this fixture.',
            'persistent_or_reusable_basis':'The fixture command is a project instruction, not a one-off user preference.'}
        return self.proposal(target_kind=kind,target_snapshot_id=aid,target_references=[{'source_id':aid}],edit=edit,instruction_review=ir)

    def test_requires_explicit_synopsis_and_outcome_inquiry(self):
        self.read_all()
        with self.assertRaisesRegex(AnalyzerError,'prerequisites'): self.finish()
        save_inquiry(self.store,self.iid,self.inquiry())
        with self.assertRaisesRegex(AnalyzerError,'synopsis'): self.finish(synopsis=None)
        saved=self.finish()['investigation']
        self.assertEqual(saved['synopsis']['text'],'The user requested a failing test, fixture repair and another check. The trace records the repair and a passing result.')

    def test_narrative_only_outcome_cannot_complete(self):
        self.read_all()
        save_inquiry(self.store,self.iid,self.inquiry(references=[{'source_id':self.ids['event-9']}]))
        with self.assertRaisesRegex(AnalyzerError,'narrative_only_outcome_inquiry'): self.finish()

    def test_unread_primary_result_and_citations_block_completion(self):
        self.read(self.ids['event-0'])
        save_inquiry(self.store,self.iid,self.inquiry())
        with self.assertRaisesRegex(AnalyzerError,'unread_cited_evidence'): self.finish()
        self.read(self.ids['event-6'])
        self.finish()

    def test_outcome_primary_classification_is_separate_from_inquiry(self):
        self.read_all();save_inquiry(self.store,self.iid,self.inquiry())
        outcome={'text':'The assistant said the check passed.','evidence_class':'recorded_observation',
                 'references':[{'source_id':self.ids['event-9']}],'limitations':[]}
        with self.assertRaisesRegex(AnalyzerError,'outcome_without_primary'): self.finish(observed_outcome=outcome)
        outcome['evidence_class']='participant_statement'
        self.finish(observed_outcome=outcome)

    def test_original_result_of_supported_incident_must_be_read(self):
        self.read(self.ids['event-0']);self.read(self.ids['event-6'])
        i=self.incident(); i['claims'][0]['references']=[{'source_id':self.ids['event-1']}]
        self.read(self.ids['event-1']);save_incident(self.store,self.iid,i)
        issues=get_diagnostic_status(self.store,self.iid)['blocking_issues']
        self.assertIn('uninspected_incident_result',{q['code'] for q in issues})
        self.read(self.ids['event-2'])
        self.assertNotIn('uninspected_incident_result',{q['code'] for q in get_diagnostic_status(self.store,self.iid)['blocking_issues']})

    def test_open_question_revisions_preserve_history_and_partial_state(self):
        self.read_all()
        first=save_inquiry(self.store,self.iid,self.inquiry(status='open',answer='Final check not yet inspected.',next_source_ids=[self.ids['event-6']]))
        with self.assertRaisesRegex(AnalyzerError,'open_material'): self.finish()
        partial=self.finish(run_status='partial',unresolved_questions=['Available final result still requires investigation.'],stop_basis='investigator_choice')['investigation']
        self.assertEqual(partial['diagnostic_review']['active_inquiries'][0]['id'],first['id'])
        self.assertEqual(partial['run_status'],'partial')

    def test_answered_revision_replaces_only_active_question(self):
        self.read_all()
        first=save_inquiry(self.store,self.iid,self.inquiry(status='open',answer='Pending read.',next_source_ids=[self.ids['event-6']]))
        second=save_inquiry(self.store,self.iid,self.inquiry(revision_of=first['id']))
        self.assertEqual([q['id'] for q in get_diagnostic_status(self.store,self.iid)['active_inquiries']],[second['id']])
        self.assertEqual(len(report_data(self.store,self.iid)['inquiries']),2)
        self.finish()

    def test_unavailable_is_not_an_available_unread_source(self):
        with self.assertRaisesRegex(AnalyzerError,'Available next sources'):
            save_inquiry(self.store,self.iid,self.inquiry(status='unavailable',next_source_ids=[self.ids['event-6']],missing_evidence=['Later external run absent.']))
        self.read_all();save_inquiry(self.store,self.iid,self.inquiry(status='unavailable',answer='External verification is absent.',references=[],missing_evidence=['External check not captured.']))
        r=self.finish(conclusion='insufficient_evidence',unresolved_questions=['External result missing.'],stop_basis='evidence_unavailable')
        self.assertEqual(r['investigation']['run_status'],'completed')

    def test_turn_reader_returns_original_call_result_and_continuation(self):
        turn=accounting(self.store,self.run)['turns'][0]
        with self.assertRaises(AnalyzerError):read_turn_evidence(self.store,self.iid,turn['id'])
        page=read_turn_evidence(self.store,self.iid,turn['id'],limit=1,max_chars=12,allow_content=True)
        self.assertEqual(page['next_tool_offset'],1)
        self.assertEqual({p['source_role'] for p in page['pages']},{'user_statement','tool_call','tool_result'})
        self.assertTrue(any(p['truncated'] for p in page['pages']))
        self.assertEqual(page['total_tools'],3)

    def test_exact_replacement_current_scope_and_net_growth(self):
        p=self.instruction();saved=save_recommendation(self.store,self.iid,p)
        self.assertEqual(saved['recommendation'],p)
        self.assertEqual(saved['validation']['status'],'ready_for_review')
        self.assertEqual(saved['validation']['edit_inspection']['net_growth']['words'],1)
        self.assertEqual(saved['validation']['edit_inspection']['net_growth']['lines'],0)
        self.assertEqual((self.root/'CLAUDE.md').read_text(),'---\nname: check-fixture\n---\nRun `python check.py`.\n')

    def test_ignored_requirement_does_not_justify_duplicate_instruction(self):
        p=self.instruction(operation='insert_after');p['instruction_review']['existing_requirement']='present_ignored'
        s=save_recommendation(self.store,self.iid,p)['validation']
        self.assertNotEqual(s['status'],'ready_for_review')
        self.assertEqual(next(c for c in s['checks'] if c['check_type']=='ignored_requirement_not_duplicated')['status'],'failed')

    def test_missing_inventory_and_ambiguous_original_cannot_be_ready(self):
        p=self.instruction();p['instruction_review']['inventory_status']='partial'
        self.assertNotEqual(save_recommendation(self.store,self.iid,p)['validation']['status'],'ready_for_review')
        p['instruction_review']['inventory_status']='complete_for_declared_scope';p['edit']['original_text']='absent exact text'
        self.assertNotEqual(save_recommendation(self.store,self.iid,p)['validation']['status'],'ready_for_review')

    def test_invocation_uses_existing_snapshot_and_no_file_growth(self):
        p=self.instruction(kind='use_existing_skill',operation='invoke');p['instruction_review']['existing_requirement']='present_ignored'
        good=save_recommendation(self.store,self.iid,p)
        self.assertEqual(good['validation']['status'],'ready_for_review')
        self.assertEqual(good['validation']['edit_inspection']['net_growth']['bytes'],0)
        p['edit']['invocation']='check-fixture'
        self.assertNotEqual(save_recommendation(self.store,self.iid,p)['validation']['status'],'ready_for_review')

    def test_new_skill_needs_scoped_inventory_review(self):
        p=self.instruction(kind='new_skill',operation='create',replacement='---\nname: fixture-check\n---\nSynthetic new procedure.\n')
        p.pop('instruction_review')
        self.assertNotEqual(save_recommendation(self.store,self.iid,p)['validation']['status'],'ready_for_review')

    def test_new_file_must_not_name_an_existing_admitted_target(self):
        p=self.instruction(kind='new_skill',operation='create',replacement='---\nname: other\n---\nA new procedure.\n')
        s=save_recommendation(self.store,self.iid,p)
        self.assertNotEqual(s['validation']['status'],'ready_for_review')
        self.assertIn('existing current snapshot',s['validation']['edit_inspection']['reason'])
        p['edit']['target_path']=str(self.root/'new-skill'/'SKILL.md')
        self.assertEqual(save_recommendation(self.store,self.iid,p)['validation']['status'],'ready_for_review')

    def test_proposal_cannot_borrow_a_claim_from_an_unlinked_incident(self):
        self.read_all();p=self.proposal()
        i=self.incident(title='Different fixture incident');i['claims'][0]['text']='A different saved claim.'
        different=save_incident(self.store,self.iid,i)
        p['claim_ids']=different['claim_ids']
        with self.assertRaisesRegex(AnalyzerError,'linked incidents'):save_recommendation(self.store,self.iid,p)

    def test_renderer_asset_snapshot_is_stable_during_host_lifetime(self):
        data=report_data(self.store,self.iid)
        expected=render_report(data)
        with patch.object(Path,'read_text',side_effect=AssertionError('Renderer reread a changing asset')):
            self.assertEqual(render_report(data),expected)

    def test_coverage_claim_discrepancy_is_flagged_without_rewriting_text(self):
        scope={'capture_gaps':{'missing_child_traces':[{'child_agent_id':'a'},{'child_agent_id':'b'},{'child_agent_id':'a'}]}}
        authored={'synopsis':{'limitations':['3 child agent traces are missing.']}}
        checks=coverage_assertions(scope,authored)
        self.assertEqual(checks[0]['status'],'needs_review')
        self.assertEqual(checks[0]['scope_value'],2)
        self.assertEqual(authored['synopsis']['limitations'],['3 child agent traces are missing.'])
        self.assertEqual(coverage_assertions(scope,{'text':'2 child traces unavailable.'})[0]['status'],'passed')
        self.assertEqual(coverage_assertions(scope,{'text':'A child trace might be missing.'}),[])

    def test_completed_run_requires_review_of_literal_coverage_conflict(self):
        self.read_all();save_inquiry(self.store,self.iid,self.inquiry())
        syn={'text':'The requested fixture was repaired.','references':[{'source_id':self.ids['event-0']}],
             'limitations':['1 child trace missing.']}
        with self.assertRaisesRegex(AnalyzerError,'coverage_count_needs_review'):self.finish(synopsis=syn)
        self.finish(synopsis=syn,run_status='partial',unresolved_questions=['Coverage count needs review.'])
        data=report_data(self.store,self.iid)
        self.assertEqual(data['investigation']['synopsis'],syn)
        self.assertIn('Coverage count needs review',render_report(data))

    def test_unread_scope_references_cannot_be_ready(self):
        p=self.instruction();extra=self.root/'extra.md';extra.write_text('Another overlapping instruction.')
        aid=admit_artifact(self.store,extra,'Overlap','current','complete')['id']
        target=p['target_snapshot_id']
        self.run=start_session_investigation(self.store,self.aid,'session-a','Uninspected overlap',artifact_ids=[target,aid])['investigation'];self.iid=self.run['id']
        self.read_all();self.read(target)
        new=self.proposal(**{k:v for k,v in p.items() if k not in ('incident_ids','claim_ids')})
        new['instruction_review']['inspected_instruction_ids'].append(aid)
        self.assertEqual(save_recommendation(self.store,self.iid,new)['validation']['status'],'needs_evidence')

    def test_empty_replacement_is_valid_and_preserved(self):
        p=self.instruction(replacement='')
        s=save_recommendation(self.store,self.iid,p)
        self.assertEqual(s['recommendation']['edit']['replacement_text'],'')
        self.assertLess(s['validation']['edit_inspection']['net_growth']['bytes'],0)

    def test_source_export_needs_disclosure_and_does_not_inflate_model_access(self):
        before=exposure(self.store,self.iid)
        with self.assertRaises(AnalyzerError):report_data(self.store,self.iid,True)
        data=report_data(self.store,self.iid,True,True)
        self.assertEqual(before,exposure(self.store,self.iid))
        self.assertEqual(data['sources'][self.ids['event-0']]['text'],session_rows()[0]['message']['content'][0]['text'])
        self.assertNotIn('text',report_data(self.store,self.iid)['sources'][self.ids['event-0']])

    def test_source_navigation_and_original_unicode_text_are_retained(self):
        rows=session_rows();rows[0]=human(0,'Long request 😀\n'+('context <tag> & detail\n'*400)+'END_REQUEST')
        self.load(rows);data=report_data(self.store,self.iid,True,True);text=data['sources'][self.ids['event-0']]['text']
        self.assertTrue(text.endswith('END_REQUEST'))
        source=data['sources'][self.ids['event-0']]
        self.assertEqual(data['sources'][source['next']]['previous'],source['id'])
        html=render_report(data)
        self.assertIn('\\u003ctag\\u003e',html)
        self.assertNotIn('context <tag>',html)
        self.assertIn('data-ref=',html)

    def test_exact_copy_payload_is_not_a_diff_or_report(self):
        exact='Keep `literal $()` and "quotes".\n</script><script>bad()</script> 😀\n'
        p=self.instruction(replacement=exact);save_recommendation(self.store,self.iid,p)
        data=report_data(self.store,self.iid,True,True);html=render_report(data)
        payload=re.search(r'<script type="application/json" id="report-data">(.*?)</script>',html,re.S).group(1)
        self.assertEqual(json.loads(payload)['recommendations'][0]['recommendation']['edit']['replacement_text'],exact)
        self.assertNotIn('<script>bad()',html)
        self.assertIn('Copy replacement',html)
        self.assertEqual(html.count('class="proposal"'),1)

    def test_multiple_findings_link_to_turn_without_repeating_proposal(self):
        self.read_all();p=self.proposal();save_recommendation(self.store,self.iid,p)
        save_incident(self.store,self.iid,self.incident(title='A second synthetic finding'))
        d=report_data(self.store,self.iid,True,True);m=turn_incidents(d)
        self.assertEqual(len(m[d['accounting']['turns'][0]['id']]),2)
        self.assertEqual(render_report(d).count('class="proposal"'),1)

    def test_failure_details_match_counted_attempts_and_keep_evidence(self):
        from ally_analyzer.session_patterns import turn_patterns
        data=report_data(self.store,self.iid,True,True)
        first,second=data['accounting']['turns']
        # Repeated attempts are separate, while rejected/unknown/unrequested
        # outcomes and failures belonging to another pattern must not leak in.
        template=next(t for t in data['tools'] if t['id']=='tool-1')
        for tid,outcome,requested,turn in [('retry','timeout',True,first),('rejected','permission_denied',True,first),
                                          ('unknown','unknown',True,first),('unrequested','execution_failure',False,first),
                                          ('other-turn','execution_failure',True,second)]:
            tool=copy.deepcopy(template);tool.update(id=tid,outcome=outcome,requested=requested,step_id=tid)
            data['tools'].append(tool);turn['tool_ids'].append(tid)
        data['turn_patterns']=turn_patterns(data['accounting']['turns'],data['tools'])
        row=next(r for r in data['turn_patterns']['rows'] if first['id'] in r['member_turn_ids'])
        self.assertEqual(row['recorded_failures'],2)
        entries=pattern_failure_entries(data,row)
        self.assertEqual({t['id'] for _,_,t in entries},{'tool-1','retry'})
        html=render_report(data)
        self.assertIn('data-failures="'+row['id']+'"',html)
        self.assertIn('FAILED (failures=1)',html)
        self.assertIn('Full result',html);self.assertIn('Tool input',html)
        self.assertIn('A failure may be expected or later recovered.',html)
        # A metadata-only export still lists the invocations but does not add text.
        for source in data['sources'].values():source.pop('text',None)
        metadata=render_report(data)
        self.assertIn('Result text is not included in this report.',metadata)
        self.assertNotIn('FAILED (failures=1)',metadata)
        original=report_data(self.store,self.iid)
        zero=next(r for r in original['turn_patterns']['rows'] if r['recorded_failures']==0)
        self.assertNotIn('data-failures="'+zero['id']+'"',render_report(original))

    def test_zero_recommendation_states_and_partial_limits(self):
        d=report_data(self.store,self.iid)
        self.assertIn('Investigation not run',render_report(d))
        self.read_all();save_inquiry(self.store,self.iid,self.inquiry());self.finish()
        d=report_data(self.store,self.iid)
        self.assertIn('No justified change',render_report(d))
        self.assertIn('No session synopsis',render_report(report_data(self.store,start_session_investigation(self.store,self.aid,'session-a','Unrun')['investigation']['id'])))

    def test_missing_usage_stays_unknown_not_zero_in_report(self):
        rows=session_rows();rows[1]['message'].pop('usage');self.load(rows)
        d=report_data(self.store,self.iid,True,True)
        self.assertIsNone(d['accounting']['session']['prompt_tokens']['value'])
        self.assertIn('<strong>Unknown</strong>',render_report(d))

if __name__=='__main__':unittest.main()
