"""An evidence review checkpoint, with immutable drafts and attributed checks.

The runner supplies the phase boundary. This module verifies source quotations,
fresh exposure and record versions, not the truth of Claude's interpretation.
"""
from collections import Counter
from .session_scope import entities, exposure, get_run, projection
from .util import AnalyzerError, bounded, canonical, strict_json

VERSION = 'investigation-review-v1'
KINDS = ('failure_explanation', 'incident', 'inquiry', 'recommendation', 'requirement_map')


def active_versions(values, field):
    replaced = {v[field].get('revision_of') for v in values}
    return [v for v in values if v['id'] not in replaced]


def update_workflow(store, investigation_id, phase, requirement_mapping=False, semantic_consistency=False, citation_explanations=False, reader_guides=False):
    """Operator-only transition; deliberately not exposed as an MCP tool."""
    from .session_investigation import active_run
    run = active_run(store, investigation_id)
    previous = run.get('review_workflow', {})
    if phase not in ('investigate', 'review') or (phase == 'review' and previous.get('phase') != 'investigate'):
        raise AnalyzerError('Invalid review phase transition')
    if phase == 'investigate' and previous:
        raise AnalyzerError('Cannot reset an existing review workflow')
    run['review_workflow'] = dict(previous, version=VERSION, phase=phase,
                                  independent_host_required=True)
    if phase=='investigate' and requirement_mapping:
        run['review_workflow']['requirement_mapping_required']=True
    if phase=='investigate' and semantic_consistency:
        from .session_consistency import VERSION as CONSISTENCY_VERSION
        run['review_workflow']['semantic_consistency_version']=CONSISTENCY_VERSION
    if phase=='investigate' and citation_explanations:
        run['review_workflow']['citation_explanations_version']='citation-explanations-v1'
    if phase=='investigate' and reader_guides:
        run['review_workflow']['finding_reader_guides_version']='finding-reader-guides-v1'
    with store.connect() as db:
        db.execute('UPDATE session_runs SET payload=? WHERE id=?', (canonical(run), investigation_id))
    return run


def active_review_records(store, investigation_id):
    from .session_investigation import records
    return [(kind, v) for kind in KINDS for v in active_versions(records(store, investigation_id, kind), 'explanation' if kind=='failure_explanation' else kind)]


def latest_draft(store, investigation_id):
    from .session_investigation import records
    values = records(store, investigation_id, 'conclusion_draft')
    # The run stores the selected ID: timestamps alone cannot order idempotent resaves.
    selected = get_run(store, investigation_id).get('review_workflow', {}).get('latest_draft_id')
    return next((v for v in values if v['id'] == selected), None)


def request_coverage(store, run, delivered=None):
    """Task requests include SDK submissions, without claiming human origin."""
    from .session_diagnostics import inspected_reference
    from .session_investigation import accounting
    from .session_scope import instruction_updates, scope_rows
    main = {r['id'] for r in scope_rows(store, run) if r['agent_id']=='main'}
    if delivered is None:
        delivered = exposure(store,run['id'])['sources']
    turns = [t for t in accounting(store,run)['turns'] if t['request_event_id'] in main]
    missing = [{'turn_id':t['id'],'turn_number':i,'source_id':t['request_event_id']}
               for i,t in enumerate(turns,1) if not inspected_reference(store,run,{'source_id':t['request_event_id']},delivered)]
    updates = instruction_updates(store, run)
    unread_updates = [u for u in updates if not inspected_reference(store,run,{'source_id':u['source_id']},delivered)]
    unread = missing + unread_updates
    return {'main_requests':len(turns), 'fully_read':len(turns)-len(missing), 'unread_requests':unread,
            'instruction_update_sources':len(updates), 'instruction_updates_fully_read':len(updates)-len(unread_updates),
            'update_origin_counts':dict(Counter(u['origin_basis'] for u in updates)),
            'population':'captured_main_task_requests_and_structured_instruction_updates',
            'coverage_status':'empty_population' if not turns and not updates else 'partial' if unread else 'fully_delivered',
            'complete_for_observed_population':bool(turns or updates) and not unread,
            'origin_counts':dict(Counter(t['origin_basis'] for t in turns)),
            'limitation':'Reading indexed requests/updates establishes analyzer exposure only, not delivery into a past response, a complete requirement inventory, fulfillment or comprehension. Updates embedded only in ordinary prose/tool results may need source investigation; source counts are not unique obligations.'}


def get_investigation_review(store, investigation_id, limit=20, offset=0):
    from .session_investigation import records
    from .session_diagnostics import get_diagnostic_status, source_role
    bounded(limit, 1, 200, 'limit'); bounded(offset, 0, 10000000, 'offset')
    run = get_run(store, investigation_id)
    values = active_review_records(store, investigation_id)
    checks = records(store, investigation_id, 'review_check')
    checked = {v['check']['record_id']:v for v in checks}
    inventory = [{'kind':k, 'id':v['id'], 'review':checked.get(v['id'], {}).get('check'),
                  'read_with':'get_investigation_records kind=' + k + ('s' if k != 'inquiry' else '')}
                 for k, v in values]
    from .session_consistency import review_plan
    map_id=next((v['id'] for k,v in values if k=='requirement_map'),None)
    for item,(kind,value) in zip(inventory,values):
        field='explanation' if kind=='failure_explanation' else kind
        item['semantic_review']=review_plan(kind,value[field],map_id)
    draft=latest_draft(store,investigation_id)
    if draft: draft={**draft,'semantic_review':review_plan('conclusion_draft',draft['conclusion'],map_id)}
    for item in inventory:
        if item['kind'] == 'inquiry': item['read_with'] = 'get_investigation_records kind=inquiries'
    with store.connect() as db:
        access = [strict_json(r[0]) for r in db.execute(
            'SELECT payload FROM investigation_access WHERE investigation_id=? ORDER BY id', (investigation_id,))]
    searches = [{'request_id':a['request_id'], **a['request'], 'match_count':len(a['deliveries']),
                 'status':a['status'], 'phase':a.get('workflow_phase')}
                for a in access if a['operation'] == 'search']
    # Navigation only: the model chooses relevance and can page the whole trajectory.
    tools = sorted((t for t in entities(store, run, 'tool') if 'main' in t['agent_ids'] and t['requested']),
                   key=lambda t:(t.get('timestamp') or '', t['id']))[-12:]
    coverage = request_coverage(store,run)
    return {'workflow':run.get('review_workflow'), 'latest_conclusion_draft':draft,
            'request_coverage':{**coverage,'unread_requests':coverage['unread_requests'][offset:offset+limit],
                                'next_offset':offset+limit if offset+limit<len(coverage['unread_requests']) else None},
            'records':inventory[offset:offset+limit], 'total_records':len(inventory),
            'next_offset':offset+limit if offset+limit<len(inventory) else None,
            'search_history':searches[-20:], 'earlier_searches':max(0,len(searches)-20),
            'recent_main_tools':[{'tool_id':t['id'], 'name':t['name'], 'outcome':t['outcome'],
                                  'sources':{s:source_role(store,run,s) for s in t['evidence']}} for t in tools],
            'diagnostics':get_diagnostic_status(store, investigation_id),
            'limitations':'Recent tools are navigation candidates, not a recovery boundary. Search history is available in access records. Review checks are Claude judgments; exact quotations and fresh reads do not prove entailment.'}


def save_review_checks(store, investigation_id, checks):
    from .session_contract import REVIEW_CHECK
    from .session_diagnostics import inspected_reference
    from .session_investigation import active_run, put_record, records, validate_payload, validate_refs
    run = active_run(store, investigation_id)
    if run.get('review_workflow', {}).get('phase') != 'review':
        raise AnalyzerError('Review checks require the operator-started review phase')
    bounded(len(checks), 1, 20, 'checks')
    kinds = {v['id']:kind for kind,v in active_review_records(store,investigation_id)}
    allowed = set(kinds)
    historical = {v['id'] for kind in KINDS for v in records(store,investigation_id,kind)}
    draft = latest_draft(store, investigation_id)
    if draft:
        allowed.add(draft['id']);kinds[draft['id']]='conclusion_draft'
    delivered = exposure(store, investigation_id, workflow_phase='review')['sources']
    bodies = []
    for check in checks:
        validate_payload(check, REVIEW_CHECK)
        if check['record_id'] not in allowed and not (check['verdict']=='needs_revision' and check['record_id'] in historical):
            raise AnalyzerError('Review the current record or current conclusion draft; stale or foreign records cannot approve a revision')
        if run.get('review_workflow',{}).get('semantic_consistency_version') and check['record_id'] in kinds:
            from .session_consistency import validate_semantic_check
            map_id=next((rid for rid,kind in kinds.items() if kind=='requirement_map'),None)
            validate_semantic_check(check,kinds[check['record_id']],allowed,map_id)
        verified = []
        for item in check['evidence_checks']:
            # The review already supplies supports_or_contradicts beside its
            # quote; do not require the same sentence twice.
            ref = item['reference']; validate_refs(store, run, [ref], reader_facing=False)
            text, sha, _, _ = projection(store, run, ref['source_id'], include_metadata=False)
            left, right = ref.get('start_char',0), ref.get('end_char',len(text))
            at = text.find(item['quote'], left, right)
            if at < 0:
                raise AnalyzerError('Review quote does not occur verbatim in the cited source range; reread instead of reconstructing syntax')
            exact = {'source_id':ref['source_id'], 'text_sha256':sha, 'start_char':at, 'end_char':at+len(item['quote'])}
            if not inspected_reference(store, run, exact, delivered):
                raise AnalyzerError('The review host must reread each quoted source range; first-stage exposure is not an independent check')
            verified.append(exact)
        if check['verdict'] == 'supported' and not verified:
            raise AnalyzerError('A supported review requires exact, freshly inspected source evidence')
        if check['verdict'] == 'qualified' and not check['remaining_uncertainty']:
            raise AnalyzerError('A qualified review must identify the material uncertainty preserved in the wording')
        bodies.append({'check':check, 'verified_quote_ranges':verified, 'policy_version':VERSION,
                       'basis':'claude_review_not_engine_entailment'})
    # Validate the batch before appending anything.
    result = []
    for body in bodies:
        rid = put_record(store, run, 'review_check', body)
        result.append({'id':rid, **body})
    return {'saved':result, 'limitation':'The engine verified quotation and review exposure, not causal reasoning.'}


def review_checkpoint(store, run, conclusion, diagnostics):
    """Save the exact draft; allow finalization only after checks of current IDs."""
    from .session_investigation import put_record, records
    workflow = run.get('review_workflow')
    if not workflow:
        return None
    rid = put_record(store, run, 'conclusion_draft', {'conclusion':conclusion})
    workflow['latest_draft_id'] = rid
    with store.connect() as db:
        db.execute('UPDATE session_runs SET payload=? WHERE id=?', (canonical(run), run['id']))
    if workflow['phase']=='review' and conclusion['run_status']=='partial':
        return {'continue_required':True, 'draft_id':rid, 'phase':'review', 'diagnostics':diagnostics,
                'request_coverage':request_coverage(store,run),
                'next_action':'Your partial checkpoint is preserved. Map the unread main-session requests and follow the material questions they raise. Record actual unanswered inquiries rather than a generic unread-trajectory limitation. When the declared inquiry is answered or genuinely unavailable, submit completed with the supported conclusion and gaps. If work cannot continue, keep this partial checkpoint; only the host records an actual budget/interruption stop. Do not change status merely to pass.'}
    required = {v['id'] for _,v in active_review_records(store, run['id'])} | {rid}
    latest = {v['check']['record_id']:v['check'] for v in records(store, run['id'], 'review_check')}
    missing = sorted(r for r in required if r not in latest or latest[r]['verdict'] == 'needs_revision')
    from .session_consistency import stale_dependencies
    stale = {r:stale_dependencies(c,required) for r,c in latest.items() if r in required and stale_dependencies(c,required)}
    missing = sorted(set(missing) | set(stale))
    if workflow['phase'] == 'investigate' or missing:
        return {'review_required':True, 'phase':workflow['phase'], 'draft_id':rid,
                'records_needing_review':missing, 'stale_review_dependencies':stale, 'diagnostics':diagnostics,
                'next_action':('End this host turn. The runner will start a fresh Claude review host.' if workflow['phase']=='investigate'
                               else 'Read and correct the current records. Save evidence-backed review checks for these IDs, then repeat finish_investigation with exactly this conclusion. No record has been approved or frozen.')}
    # Missing evidence is a closed, supported limit. It must not disguise available unfinished work.
    if conclusion['stop_basis'] == 'evidence_unavailable' and any(i['code']=='open_material_inquiry' for i in diagnostics['blocking_issues']):
        raise AnalyzerError('Open investigation work is not unavailable evidence. Follow available sources, or preserve partial with the actual reason (investigator_choice or an observed external limit). Close only the genuinely unavailable inquiries.')
    return None
