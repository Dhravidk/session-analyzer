import copy
import json
import unittest
from ally_analyzer.session_consistency import writing_signals
from ally_analyzer.session_investigation import accounting, save_incident, validate_refs
from ally_analyzer.session_requirements import save_requirement_map, map_coverage
from ally_analyzer.session_review import get_investigation_review, request_coverage, save_review_checks, update_workflow
from ally_analyzer.session_report import report_data, render_report
from ally_analyzer.session_scope import get_run
from ally_analyzer.util import AnalyzerError
from tests import test_session_workflow as workflow
from tests.test_session_workflow import session_rows
from tests import test_session_diagnostics as diagnostics
from tests import test_session_review as review
from tests import test_session_evidence as evidence
from tests.helpers import response


class ConsistencyTests(unittest.TestCase):
    contract_version='single-session-v2'
    setUp=workflow.SessionWorkflowTests.setUp
    load=workflow.SessionWorkflowTests.load
    read=workflow.SessionWorkflowTests.read
    read_all=diagnostics.DiagnosticTests.read_all
    finish=diagnostics.DiagnosticTests.finish
    inquiry=diagnostics.DiagnosticTests.inquiry
    incident=diagnostics.DiagnosticTests.incident
    refs=evidence.EvidenceTests.refs
    verification=evidence.EvidenceTests.verification
    requirement=evidence.EvidenceTests.requirement
    mapped=evidence.EvidenceTests.mapped
    check=review.ReviewWorkflowTests.check

    def strict(self):
        from ally_analyzer.session_diagnostics import save_inquiry
        from ally_analyzer.session_failures import save_failure_explanation
        from tests.test_session_failures import FailureExplanationTests
        update_workflow(self.store,self.iid,'investigate',requirement_mapping=True,semantic_consistency=True)
        self.read_all();save_inquiry(self.store,self.iid,self.inquiry())
        save_failure_explanation(self.store,self.iid,FailureExplanationTests.explanation(self))
        self.mapping=save_requirement_map(self.store,self.iid,self.mapped())
        self.draft=self.finish()['draft_id']
        update_workflow(self.store,self.iid,'review');self.read_all()

    def semantic_check(self, item):
        plan=item['semantic_review']
        return self.check(item['id'],semantic_checks=[{'aspect':aspect,'verdict':'consistent',
            'assessment':'Synthetic contract check only; independent semantic correctness is not established.',
            'related_record_ids':[plan['current_requirement_map_id']] if aspect=='opening_requirement_consistency' and plan['current_requirement_map_id'] else []}
            for aspect in plan['required_aspects']])

    def test_sdk_requests_are_in_task_population_but_not_human_turns(self):
        rows=session_rows()
        for i in (0,8):rows[i]['turnOrigin']='sdk'
        self.load(rows);a=accounting(self.store,self.run)
        self.assertEqual(a['session']['task_requests']['value'],2)
        self.assertEqual(a['session']['human_origin_turns']['value'],0)
        self.assertEqual(a['session']['user_turns']['value'],0)
        self.assertEqual(len(a['turns']),2)
        self.assertEqual(a['attribution_coverage']['responses_without_unambiguous_turn'],[])
        coverage=request_coverage(self.store,self.run)
        self.assertEqual(coverage['main_requests'],2);self.assertEqual(coverage['fully_read'],0)
        self.assertFalse(coverage['complete_for_observed_population'])
        self.read_all();self.assertEqual(request_coverage(self.store,self.run)['coverage_status'],'fully_delivered')
        data=report_data(self.store,self.iid,True,True)
        self.assertIn('2</strong> task requests',render_report(data))
        self.assertEqual(data['main_accounting']['session']['human_origin_turns']['value'],0)

    def test_empty_request_population_does_not_establish_coverage(self):
        self.load([response(0)])
        coverage=request_coverage(self.store,self.run)
        self.assertEqual(coverage['coverage_status'],'empty_population')
        self.assertFalse(coverage['complete_for_observed_population'])
        self.assertFalse(accounting(self.store,self.run)['session']['task_requests']['complete_for_observed_population'])
        self.assertEqual(map_coverage(self.store,self.run,{'requirements':[],'context_only':[]})['coverage_status'],'empty_population')

    def test_semantic_checks_required_and_qualification_cannot_approve_contradiction(self):
        self.strict();packet=get_investigation_review(self.store,self.iid)
        item=next(r for r in packet['records'] if r['kind']=='requirement_map')
        with self.assertRaisesRegex(AnalyzerError,'semantic aspects'):save_review_checks(self.store,self.iid,[self.check(item['id'])])
        check=self.semantic_check(item)
        check['semantic_checks'][0].update(verdict='needs_revision',assessment='The completed bundle includes a missed material instruction; separate the outcomes.')
        check.update(verdict='qualified',remaining_uncertainty=['The procedural obligation remains missed.'])
        with self.assertRaisesRegex(AnalyzerError,'contradiction'):save_review_checks(self.store,self.iid,[check])
        check['verdict']='needs_revision';save_review_checks(self.store,self.iid,[check])
        self.assertIn(item['id'],self.finish()['records_needing_review'])

    def test_revised_map_invalidates_an_unchanged_opening_review(self):
        self.strict();packet=get_investigation_review(self.store,self.iid)
        for item in packet['records']+[packet['latest_conclusion_draft']]:save_review_checks(self.store,self.iid,[self.semantic_check(item)])
        revised=save_requirement_map(self.store,self.iid,self.mapped(revision_of=self.mapping['id'],
                    requirements=[self.requirement(status='unverified',missing_evidence=['A material part remains unverified.'])]))
        pending=self.finish()
        self.assertIn(revised['id'],pending['records_needing_review'])
        self.assertIn(self.draft,pending['records_needing_review'])
        self.assertEqual(pending['stale_review_dependencies'][self.draft],[self.mapping['id']])

    def test_generic_citation_labels_rejected_without_changing_existing_outputs(self):
        self.strict()
        for label in ('Error text.','Denial message','This supports the analysis.'):
            with self.assertRaisesRegex(AnalyzerError,'linked claim'):
                validate_refs(self.store,get_run(self.store,self.iid),[{'source_id':self.ids['event-6'],'explanation':label}])
        validate_refs(self.store,get_run(self.store,self.iid),[{'source_id':self.ids['event-6'],
            'explanation':'The full fixture check passed after the edit, supporting the recorded recovery.'}])

    def test_expected_requires_basis_but_recovered_unexpected_needs_no_proposal(self):
        update_workflow(self.store,self.iid,'investigate',semantic_consistency=True)
        self.read_all()
        with self.assertRaisesRegex(AnalyzerError,'Common, harmless or recovered'):
            save_incident(self.store,self.iid,self.incident(expectedness='expected'))
        saved=save_incident(self.store,self.iid,self.incident(expectedness='unexpected',remaining_action='none'))
        self.assertEqual(saved['incident']['remaining_action'],'none')
        expected=self.incident(expectedness='expected',expectedness_basis={'category':'intentional_negative_check',
            'references':self.refs('event-0'),'explanation':'The synthetic request explicitly asks to run a failing test before repair.'})
        self.assertEqual(save_incident(self.store,self.iid,expected)['incident'],expected)

    def test_citation_identity_does_not_include_its_contextual_explanation(self):
        self.read_all()
        first={**self.refs('event-9')[0],'explanation':'The assistant delivers the requested explanation in this response.'}
        second={**first,'explanation':'This response is the delivered text being assessed for the explanation requirement.'}
        requirement=self.requirement(result_references=[first],verification_required=False,verification=[],
            delivered_response_evidence={'references':[second],'basis':'Requested text is the deliverable.'})
        self.assertEqual(save_requirement_map(self.store,self.iid,self.mapped([requirement]))['requirement_map']['requirements'][0],requirement)

    def test_writing_signals_identify_literal_repetition_without_rewriting(self):
        text='The full fixture check passed after the recorded edit.'
        value={'synopsis':{'text':text},'observed_outcome':{'text':text},'summary':'The scope and revision match.'}
        before=copy.deepcopy(value);signals=writing_signals(value,'conclusion_draft')
        self.assertEqual(signals[0]['fields'],['outcome','synopsis']);self.assertEqual(value,before)

    def test_review_disagreement_visible_beside_saved_expectedness(self):
        self.read_all();saved=save_incident(self.store,self.iid,self.incident(expectedness='expected'))
        data=report_data(self.store,self.iid,True,True)
        data['review_checks']=[{'id':'synthetic-check','check':self.check(saved['id'],verdict='qualified',
            assessment='The failure was a read probe; expectedness was not established.',remaining_uncertainty=['The intended negative-test purpose was not recorded.'])}]
        before=copy.deepcopy(data);html=render_report(data)
        dialog=html[html.index('id="finding-'+saved['id']):]
        self.assertLess(dialog.index('Claude review · qualified'),dialog.index('class="claim"'))
        self.assertIn('expected ·',dialog);self.assertIn('expectedness was not established',dialog)
        self.assertEqual(data,before)


if __name__=='__main__':unittest.main()
