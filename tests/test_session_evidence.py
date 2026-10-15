"""Synthetic adversarial requirements, episode, resource and attribution tests."""
import copy
import json
import unittest

from ally_analyzer.session_requirements import save_requirement_map, current_map
from ally_analyzer.session_resources import get_context_timeline, get_tool_output_index
from ally_analyzer.session_episodes import measure_recovery_episodes
from ally_analyzer.session_investigation import accounting, measure_selection, save_incident
from ally_analyzer.session_scope import entities, start_session_investigation
from ally_analyzer.session_validation import admit_artifact
from ally_analyzer.session_report import report_data, render_report
from ally_analyzer.util import AnalyzerError
from tests import test_session_diagnostics as diagnostic
from tests.test_session_workflow import session_rows, human
from tests.helpers import call, response, result, usage


class EvidenceTests(unittest.TestCase):
    contract_version='single-session-v2'
    setUp=diagnostic.DiagnosticTests.setUp
    load=diagnostic.DiagnosticTests.load
    read=diagnostic.DiagnosticTests.read
    read_all=diagnostic.DiagnosticTests.read_all
    incident=diagnostic.DiagnosticTests.incident

    def refs(self,*names): return [{'source_id':self.ids[n]} for n in names]

    def verification(self,**changes):
        value={'description':'Synthetic full check after repair.', 'references':self.refs('event-6'), 'outcome':'passed',
               'scope_relation':'same','revision_relation':'current','basis':'The recorded full check follows the fixture edit.',
               'check_event_id':self.ids['event-6'],'relevant_change_event_ids':[self.ids['event-4']]}
        value.update(changes);return value

    def requirement(self,**changes):
        value={'key':'repair','description':'Repair the fixture and check it.','scope':'Synthetic fixture only.',
               'intent_references':self.refs('event-0'),'status':'supported_completed','status_basis':'The full check passed after the edit.',
               'result_references':self.refs('event-4','event-6'),'verification_required':True,'verification':[self.verification()],
               'artifact_revision':{'state':'unknown','references':[]},'intent_changes':[],'merged_from':[],'superseded_by':[],'missing_evidence':[]}
        value.update(changes);return value

    def mapped(self,requirements=None,**changes):
        value={'scope':'Synthetic repair, excluding explanatory prose.','inventory_status':'partial',
               'requirements':requirements if requirements is not None else [self.requirement()],
               'context_only':[],'limitations':['Only the repair procedure is mapped.'],
               'provenance':{'model':'synthetic-test','skill_version':'evidence-fixture-v1'}}
        value.update(changes);return value

    def episode(self,**changes):
        rs={r['evidence'][0]:r['id'] for r in entities(self.store,self.run,'response')}
        attempts=[]
        for key,role,start,end in [('original','original',1,2),('fix','corrective',3,4),('check','verification',5,6)]:
            attempts.append({'key':key,'role':role,'description':'Synthetic '+role,'same_goal_basis':'The fixture path and full check scope match.',
                             'event_ids':[self.ids['event-'+str(start)],self.ids['event-'+str(end)]],
                             'tool_ids':['tool-'+str(start)],'response_ids':[rs[self.ids['event-'+str(start)]]]})
        ep={'intended_result':'Repair and verify the synthetic fixture.','goal_references':self.refs('event-0'),
            'attempts':attempts,'verification':[self.verification()],'membership_justification':'Same fixture and requested full check.','limitations':[]}
        i=self.incident(member_event_ids=[s for a in attempts for s in a['event_ids']],tool_ids=['tool-1','tool-3','tool-5'],episode=ep)
        i.update(changes);return i

    def attribution(self,**changes):
        value={'category':'instruction_nonadherence','support':'not_established','component':'Synthetic check skill','version':'Unknown',
               'version_basis':'unknown','component_references':[], 'instruction_references':[],
               'execution_references':self.refs('event-5','event-6'),'agent_ids':['main'],
               'basis':'The task result alone does not establish plugin fault.','alternatives':[],
               'missing_evidence':['The instructions and installed version are absent.'],
               'immediate_next_action':'Inspect applicable instructions before assigning fault.','persistent_change_basis':'No persistent change is justified.'}
        value.update(changes);return value

    def test_narrowed_retry_is_not_completed_requirement_or_recovered_episode(self):
        self.read_all();check=self.verification(scope_relation='narrower',basis='Only one of the requested cases ran.')
        with self.assertRaisesRegex(AnalyzerError,'same-goal'):save_requirement_map(self.store,self.iid,self.mapped([self.requirement(verification=[check])]))
        saved=save_requirement_map(self.store,self.iid,self.mapped([self.requirement(status='unverified',verification=[check],missing_evidence=['Full requested cases not checked.'])]))
        self.assertIn('verification_scope_narrower',saved['verification_prerequisites']['repair'][0]['qualifications'])
        i=self.episode();i['episode']['verification']=[check]
        with self.assertRaisesRegex(AnalyzerError,'narrower'):save_incident(self.store,self.iid,i)
        i['resolution']='unknown';self.assertEqual(save_incident(self.store,self.iid,i)['incident'],i)

    def test_changed_command_can_genuinely_recover_same_goal(self):
        rows=session_rows();rows[5]['message']['content'][0]['input']['command']='python3 -m unittest discover -s tests'
        self.load(rows);self.read_all()
        i=self.episode();i['episode']['verification'][0]['basis']='The discovery command covers the same fixture test.'
        saved=save_incident(self.store,self.iid,i)
        measured=measure_recovery_episodes(self.store,self.iid,[saved['id']])
        self.assertEqual(measured['metrics']['tool_invocations']['value'],3)
        self.assertEqual(measured['metrics']['prompt_tokens']['value'],180)
        self.assertEqual(measured['metrics']['completion_tokens']['value'],120)
        self.assertEqual(measured['metrics']['recorded_tool_duration_ms']['value'],None)

    def test_stale_check_cannot_verify_changed_artifact_even_if_model_says_current(self):
        rows=session_rows()+[call(10,name='Edit'),result(11,'tool-10')]
        self.load(rows);self.read_all()
        check=self.verification(relevant_change_event_ids=[self.ids['event-11']])
        with self.assertRaisesRegex(AnalyzerError,'relevant revision'):save_requirement_map(self.store,self.iid,self.mapped([self.requirement(verification=[check])]))
        saved=save_requirement_map(self.store,self.iid,self.mapped([self.requirement(status='unverified',verification=[check],missing_evidence=['No check after the latest change.'])]))
        self.assertEqual(saved['verification_prerequisites']['repair'][0]['predates_change_event_ids'],[self.ids['event-11']])

    def test_completion_claim_without_result_cannot_be_promoted(self):
        self.read_all()
        with self.assertRaisesRegex(AnalyzerError,'primary result'):
            save_requirement_map(self.store,self.iid,self.mapped([self.requirement(result_references=self.refs('event-9'),verification_required=False)]))

    def test_requested_response_can_be_delivered_without_tool_execution_or_user_acceptance(self):
        requirement=self.requirement()
        rows=[human(0,'Explain that cached input is included in total input.'),
              response(1,content=[{'type':'text','text':'Total input includes uncached input, cache creation and cache reads; do not add cached input again.'}])]
        self.load(rows);self.read_all()
        delivered={'references':self.refs('event-1'),'basis':'The user requested explanatory text, and the recorded response supplies that explanation.'}
        requirement.update(description='Explain input accounting.',scope='Requested response content.',intent_references=self.refs('event-0'),
            result_references=self.refs('event-1'),verification_required=False,verification=[],
            status_basis='The explanation is the deliverable; no execution or user acceptance was requested.',delivered_response_evidence=delivered)
        saved=save_requirement_map(self.store,self.iid,self.mapped([requirement]))
        self.assertEqual(saved['requirement_map']['requirements'][0]['delivered_response_evidence'],delivered)
        self.assertIn(delivered['basis'],render_report(report_data(self.store,self.iid)))

    def test_delivered_response_cannot_use_request_tool_call_or_uncited_text(self):
        self.read_all()
        for sid in ('event-0','event-1'):
            with self.subTest(source=sid), self.assertRaisesRegex(AnalyzerError,'retained assistant text'):
                save_requirement_map(self.store,self.iid,self.mapped([self.requirement(result_references=self.refs(sid),
                    verification_required=False,verification=[],delivered_response_evidence={'references':self.refs(sid),'basis':'Synthetic invalid source.'})]))
        with self.assertRaisesRegex(AnalyzerError,'result_references'):
            save_requirement_map(self.store,self.iid,self.mapped([self.requirement(delivered_response_evidence={
                'references':self.refs('event-9'),'basis':'The response was not included in result evidence.'})]))

    def test_delivered_response_does_not_override_required_execution_verification(self):
        self.read_all()
        with self.assertRaisesRegex(AnalyzerError,'same-goal check'):
            save_requirement_map(self.store,self.iid,self.mapped([self.requirement(result_references=self.refs('event-9'),
                verification=[],delivered_response_evidence={'references':self.refs('event-9'),'basis':'A text delivery cannot establish a required test passed.'})]))

    def test_requirement_revision_cannot_drop_intent_and_can_merge_duplicates(self):
        self.read_all();first=save_requirement_map(self.store,self.iid,self.mapped([self.requirement(),self.requirement(key='duplicate',description='Run the repair check.')]));before=copy.deepcopy(first)
        with self.assertRaisesRegex(AnalyzerError,'silently drop'):
            save_requirement_map(self.store,self.iid,self.mapped(revision_of=first['id']))
        second=save_requirement_map(self.store,self.iid,self.mapped([self.requirement(merged_from=['duplicate'])],revision_of=first['id']))
        self.assertEqual(first,before);self.assertEqual(current_map(self.store,self.iid)['id'],second['id'])
        self.assertEqual(len(report_data(self.store,self.iid)['requirement_map_history']),2)

    def test_withdrawal_needs_changed_intent_and_preserves_original(self):
        self.read_all()
        r=self.requirement(status='withdrawn',verification=[])
        with self.assertRaisesRegex(AnalyzerError,'intent'):save_requirement_map(self.store,self.iid,self.mapped([r]))
        r['intent_changes']=[{'description':'Synthetic correction, asserted by the test author only.','references':self.refs('event-8')}]
        saved=save_requirement_map(self.store,self.iid,self.mapped([r]))
        self.assertEqual(saved['requirement_map']['requirements'][0]['intent_references'],self.refs('event-0'))

    def test_overlapping_episodes_count_union_once_exclude_intervening_work(self):
        rows=session_rows()+[call(10,name='Read'),result(11,'tool-10')]
        self.load(rows);self.read_all()
        first=save_incident(self.store,self.iid,self.episode())
        second=save_incident(self.store,self.iid,self.episode(title='Another view of the same synthetic recovery'))
        union=measure_recovery_episodes(self.store,self.iid,[first['id'],second['id']])
        self.assertEqual(union['metrics']['prompt_tokens']['value'],180)
        self.assertEqual(union['metrics']['tool_invocations']['value'],3)
        self.assertNotIn('tool-10',union['selection']['tool_ids'])
        self.assertEqual(len(union['overlapping_identities_counted_once']['response_ids']),3)
        self.assertEqual(len(union['observed_intervals']),1)

    def test_expected_failure_and_correct_denial_need_no_recommendation(self):
        rows=session_rows()+[call(10,args={'command':'send-private-data'}),result(11,'tool-10','Permission for this action was denied',True)]
        self.load(rows);self.read_all();save_incident(self.store,self.iid,self.episode())
        denial=self.incident(title='Synthetic correct denial',member_event_ids=[self.ids['event-10'],self.ids['event-11']],tool_ids=['tool-10'],resolution='not_applicable',recovery_references=[])
        denial['claims'][0].update(text='The policy denied the action.',references=self.refs('event-11'))
        save_incident(self.store,self.iid,denial)
        data=report_data(self.store,self.iid);self.assertEqual(data['recommendations'],[])
        self.assertEqual([i['incident']['remaining_action'] for i in data['incidents']],['none','none'])

    def test_cache_drop_does_not_invent_compaction_and_ratio_population_matches(self):
        rows=[human(0),response(1,u=usage(10,10,980)),response(2,u=usage(10,10,0)),response(3,u={'input_tokens':1,'output_tokens':2})]
        self.load(rows)
        view=get_context_timeline(self.store,self.iid)
        self.assertEqual(view['coverage']['recorded_compaction_count'],0)
        self.assertEqual([p['kind'] for p in view['items']],['turn_boundary','response','response','response'])
        from ally_analyzer.session_resources import context_timeline
        share=context_timeline(self.store,self.run)['cache_read_share'];self.assertIsNone(share['value'])
        self.assertEqual(share['numerator_response_ids'],share['denominator_response_ids'])
        self.assertEqual(share['denominator'],1020);self.assertAlmostEqual(share['known_population_ratio'],980/1020)
        self.assertEqual(view['peak_input']['known_maximum'],1000);self.assertIsNone(view['peak_input']['value'])

    def test_recorded_compaction_before_after_components_and_duration(self):
        compact={'type':'system','subtype':'compact_boundary','uuid':'compact','sessionId':'session-a','timestamp':'2026-09-01T12:00:02Z',
                 'compactMetadata':{'trigger':'auto','preTokens':1000,'postTokens':100,'durationMs':350}}
        rows=[human(0),response(1,u=usage(10,10,980)),compact,response(3,u=usage(80,20,0))]
        rows[-1]['message']['model']='second-synthetic-model';self.load(rows)
        view=get_context_timeline(self.store,self.iid)
        boundary=next(p for p in view['items'] if p['kind']=='recorded_compaction')
        self.assertEqual(boundary['recorded_duration_ms'],350)
        self.assertEqual(boundary['cache_read_percentage_point_change'],-98)
        self.assertEqual(boundary['before']['tokens']['total_input_tokens'],1000)
        self.assertEqual(boundary['after']['tokens']['cache_creation_input_tokens'],20)
        self.assertEqual(sum(p['kind']=='model_change' for p in view['items']),1)
        page=get_context_timeline(self.store,self.iid,limit=1);self.assertEqual(page['next_offset'],1)

    def test_registered_resource_formulas_and_output_disclosure(self):
        rows=[human(0),call(1,name='Read',args={'file_path':'/synthetic/x'}),result(2,'tool-1','Output truncated\n🙂'),call(3,name='Read',args={'file_path':'/synthetic/x'}),result(4,'tool-3','Output truncated\n🙂')]
        self.load(rows)
        view=get_tool_output_index(self.store,self.iid)
        self.assertEqual(view['items'][0]['truncation_detection'],'not_run')
        with self.assertRaises(AnalyzerError):get_tool_output_index(self.store,self.iid,inspect_markers=True)
        view=get_tool_output_index(self.store,self.iid,inspect_markers=True,allow_content=True)
        self.assertEqual(view['items'][0]['same_input_count'],2)
        group=get_tool_output_index(self.store,self.iid,same_input_as='tool-1',limit=1)
        self.assertEqual(group['total'],2);self.assertEqual(group['next_offset'],1)
        self.assertEqual(view['items'][0]['captured_result_bytes'],len('Output truncated\n🙂'.encode()))
        self.assertTrue(view['items'][0]['truncation_marker_source_ids'])
        for formula,expected in [('uncached_input_tokens',20),('cache_creation_tokens',40),('peak_input_tokens',60),('cache_read_share',.5),('captured_tool_result_bytes',42)]:
            measured=measure_selection(self.store,self.iid,formula,{'all_scoped':True,'membership_basis':'Synthetic whole captured scope.'})
            self.assertEqual(measured['value'],expected,formula)

    def test_current_skill_snapshot_does_not_establish_historical_fault(self):
        path=self.root/'SKILL.md';path.write_text('Synthetic skill v2. Run the full suite after the last edit.\n')
        aid=admit_artifact(self.store,path,'Synthetic current skill','current','complete','v2')['id']
        self.run=start_session_investigation(self.store,self.aid,'session-a','Synthetic version check',artifact_ids=[aid])['investigation'];self.iid=self.run['id']
        self.read_all();self.read(aid)
        a=self.attribution(support='established',version='v2',version_basis='historical',component_references=[{'source_id':aid}],instruction_references=[{'source_id':aid}])
        with self.assertRaisesRegex(AnalyzerError,'nonhistorical_snapshot'):save_incident(self.store,self.iid,self.incident(attribution=a))
        a.update(support='not_established',version_basis='current_only')
        saved=save_incident(self.store,self.iid,self.incident(attribution=a))
        self.assertIn('historical_component_version_not_established',saved['attribution_prerequisites']['qualifications'])

    def test_adequate_historical_instructions_can_support_nonadherence_without_new_rule(self):
        path=self.root/'historical.md';path.write_text('Synthetic v1: check the full suite after each final change.\n')
        aid=admit_artifact(self.store,path,'Synthetic historical skill','historical','complete','v1')['id']
        self.run=start_session_investigation(self.store,self.aid,'session-a','Synthetic version check',artifact_ids=[aid])['investigation'];self.iid=self.run['id']
        self.read_all();self.read(aid)
        a=self.attribution(support='established',version='v1',version_basis='historical',component_references=[{'source_id':aid}],instruction_references=[{'source_id':aid}],missing_evidence=[])
        saved=save_incident(self.store,self.iid,self.incident(attribution=a))
        self.assertEqual(saved['attribution_prerequisites']['qualifications'],[])
        self.assertIn('operator reported',saved['attribution_prerequisites']['limitation'])
        self.assertEqual(report_data(self.store,self.iid)['recommendations'],[])

    def test_missing_child_prevents_established_agent_fault(self):
        rows=session_rows()+[call(10,name='Agent',args={'prompt':'Synthetic check'}),result(11,'tool-10','Launched',meta={'agentId':'missing-child','status':'running'})]
        self.load(rows);self.read_all()
        a=self.attribution(category='handoff_or_verification',support='established',execution_references=self.refs('event-11'),agent_ids=['missing-child'])
        i=self.incident(resolution='unknown',recovery_references=[],attribution=a)
        with self.assertRaisesRegex(AnalyzerError,'missing_agent_trace'):save_incident(self.store,self.iid,i)
        a.update(support='not_established',missing_evidence=['Child trace unavailable; launch acknowledgment is not a check result.'])
        self.assertEqual(save_incident(self.store,self.iid,i)['attribution_prerequisites']['unavailable_agent_ids'],['missing-child'])

    def test_report_preserves_saved_requirement_and_measurement_data(self):
        import html
        import re
        self.read_all();saved=save_requirement_map(self.store,self.iid,self.mapped());i=save_incident(self.store,self.iid,self.episode(attribution=self.attribution()))
        data=report_data(self.store,self.iid,include_source_text=True,allow_content=True);rendered=render_report(data)
        self.assertEqual(data['requirement_map']['requirement_map'],saved['requirement_map'])
        for expected in ('Requirements ·','Context and cache timeline','Captured tool outputs','Recovery episode','Cache write','Recorded execution durations'):
            self.assertIn(expected,rendered)
        self.assertEqual(data['episode_resources'][i['id']]['metrics']['prompt_tokens']['value'],180)
        self.assertIn('requirements',json.dumps(data))
        contexts=[json.loads(html.unescape(v)) for v in re.findall(r'data-source-context="([^"]*)"',rendered)]
        requirement=saved['requirement_map']['requirements'][0]
        for owner,text in ((saved['id'],requirement['status_basis']),
                           (saved['id'],requirement['verification'][0]['basis']),
                           (i['id'],i['incident']['episode']['intended_result']),
                           (i['id'],i['incident']['episode']['attempts'][0]['same_goal_basis']),
                           (i['id'],i['incident']['attribution']['basis'])):
            self.assertTrue(any(c['owner_id']==owner and c['text']==text for c in contexts))
        payload=json.loads(re.search(r'id="report-data">(.*?)</script>',rendered,re.S).group(1))
        self.assertEqual(payload,data)

    def test_shared_child_execution_is_not_confident_fault_attribution(self):
        from tests.test_session_agents import linked_fixture
        from tests.helpers import write_log
        from ally_analyzer.ingest import import_bundle
        from ally_analyzer.engine import analyze_dataset
        from ally_analyzer.session_scope import scope_rows
        path=linked_fixture(self.root/'linked')
        child=path.parent/'session-a/subagents/agent-child-a.jsonl'
        rows=[json.loads(line) for line in child.read_text().splitlines()]
        rows.append(response(91,mid='msg-90',request='req-90',content=[{'type':'text','text':'Copied provider response.'}]))
        write_log(child,rows)
        self.aid=analyze_dataset(self.store,import_bundle(self.store,path)['dataset_id'])['analysis_id']
        self.run=start_session_investigation(self.store,self.aid,'session-a','Synthetic shared identity attribution')['investigation'];self.iid=self.run['id']
        self.ids={json.loads(r['raw']).get('uuid'):r['id'] for r in scope_rows(self.store,self.run)};self.read_all()
        a=self.attribution(category='handoff_or_verification',support='established',execution_references=self.refs('event-91'),agent_ids=['child-a'])
        i=self.incident(resolution='unknown',recovery_references=[],attribution=a)
        with self.assertRaisesRegex(AnalyzerError,'ambiguous_shared_execution_identity'):save_incident(self.store,self.iid,i)
        a.update(support='not_established',missing_evidence=['The copied response cannot be assigned to one agent.'])
        saved=save_incident(self.store,self.iid,i)
        self.assertTrue(saved['attribution_prerequisites']['shared_execution_ids'])
        timeline=get_context_timeline(self.store,self.iid,agent_id='child-a')
        self.assertTrue(timeline['coverage']['shared_response_ids_excluded'])

    def test_recorded_execution_sum_is_separate_from_elapsed_interval(self):
        rows=session_rows();rows[2]['toolUseResult']={'durationMs':250};rows[4]['toolUseResult']={'durationMs':50};rows[6]['toolUseResult']={'durationMs':350}
        self.load(rows);self.read_all();saved=save_incident(self.store,self.iid,self.episode())
        m=measure_recovery_episodes(self.store,self.iid,[saved['id']])
        self.assertEqual(m['metrics']['recorded_tool_duration_ms']['value'],650)
        self.assertEqual(m['observed_intervals'][0]['observed_elapsed_seconds'],5)
        self.assertIn('not active recovery time',m['observed_intervals'][0]['limitation'])

    def test_structurally_linked_child_can_verify_parent_recovery_without_adding_spans(self):
        from tests.helpers import write_log
        from ally_analyzer.ingest import import_bundle
        from ally_analyzer.engine import analyze_dataset
        from ally_analyzer.session_scope import scope_rows
        folder=self.root/'cross-agent';child=folder/'session-a/subagents'
        parent=write_log(folder/'session-a.jsonl',[human(0),call(1),result(2,'tool-1','Synthetic original failed',True),
            call(3,'Agent',{'prompt':'Repair and verify the same fixture.'}),result(4,'tool-3','Launched',meta={'agentId':'child-a','status':'running'})])
        write_log(child/'agent-child-a.jsonl',[call(5,args={'command':'python -m unittest discover'}),result(6,'tool-5','Synthetic same fixture passed.')])
        self.aid=analyze_dataset(self.store,import_bundle(self.store,parent)['dataset_id'])['analysis_id']
        self.run=start_session_investigation(self.store,self.aid,'session-a','Synthetic linked recovery')['investigation'];self.iid=self.run['id']
        self.ids={json.loads(r['raw']).get('uuid'):r['id'] for r in scope_rows(self.store,self.run)};self.read_all()
        i=self.episode();i['episode']['verification']=[self.verification(relevant_change_event_ids=[],revision_relation='not_applicable',basis='Synthetic child check verifies the original requested goal.')]
        saved=save_incident(self.store,self.iid,i);resources=measure_recovery_episodes(self.store,self.iid,[saved['id']])
        self.assertEqual(resources['metrics']['llm_calls']['value'],3)
        self.assertEqual({v['agent_id'] for v in resources['observed_intervals']},{'main','child-a'})
        self.assertNotIn('combined_elapsed_seconds',resources)

    def test_resource_pages_do_not_repeat_whole_populations(self):
        rows=[human(0)]+[response(i) for i in range(1,601)]
        self.load(rows)
        page=get_context_timeline(self.store,self.iid,limit=2)
        self.assertLess(len(json.dumps(page).encode()),12000)
        self.assertEqual(page['cache_read_share']['eligible'],600)
        self.assertEqual(page['cache_read_share']['identity_counts']['numerator_response_ids'],600)
        self.assertEqual(len(page['cache_read_share']['identity_previews']['numerator_response_ids']),5)
        self.assertEqual(page['next_offset'],2)

    def test_registered_before_after_changes_and_compaction_duration(self):
        compact={'type':'system','subtype':'compact_boundary','uuid':'compact','sessionId':'session-a','timestamp':'2026-09-01T12:00:02Z',
                 'compactMetadata':{'preTokens':1000,'postTokens':100,'durationMs':350}}
        self.load([human(0),response(1,u=usage(10,10,980)),compact,response(3,u=usage(80,20,0))])
        rs=sorted(entities(self.store,self.run,'response'),key=lambda r:r['timestamp'])
        selection={'response_ids':[r['id'] for r in rs],'membership_basis':'Recorded before and after responses.'}
        for formula,expected in [('input_change_tokens',-900),('cache_read_share_change_pp',-98)]:
            m=measure_selection(self.store,self.iid,formula,selection);self.assertEqual(m['value'],expected)
            self.assertEqual(m['before_response_id'],rs[0]['id'])
        m=measure_selection(self.store,self.iid,'recorded_compaction_duration_ms',{'event_ids':[self.ids['compact']],'membership_basis':'Actual recorded compact boundary.'})
        self.assertEqual(m['value'],350)
        selection['response_ids'].reverse()
        with self.assertRaisesRegex(AnalyzerError,'before/after order'):measure_selection(self.store,self.iid,'input_change_tokens',selection)

    def test_repeated_retrieval_index_has_linear_identity_storage(self):
        rows=[human(0)]
        for i in range(1,101,2):rows.extend([call(i,'Read',{'file_path':'/synthetic/repeated'}),result(i+1,'tool-'+str(i),'Same saved result')])
        self.load(rows)
        from ally_analyzer.session_resources import tool_output_index
        raw=tool_output_index(self.store,self.run)
        self.assertEqual(sum(len(v) for v in raw['input_groups'].values()),50)
        page=get_tool_output_index(self.store,self.iid,same_result_as='tool-1',limit=2)
        self.assertEqual(page['total'],50);self.assertEqual(page['items'][0]['same_result_count'],50)
        self.assertLess(len(json.dumps(page).encode()),9000)


if __name__=='__main__':unittest.main()
