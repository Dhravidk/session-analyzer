"""Evidence prerequisites and inquiry history. Not a semantic correctness score."""
import re
from .session_contract import INQUIRY
from .session_scope import (entities, exposure, get_run, get_scope, projection, read_investigation_evidence,
                            source_record, scope_rows)
from .normalize import content_blocks
from .util import AnalyzerError, bounded, strict_json

VERSION = 'diagnostic-review-v2'


def coverage_assertions(scope, fields):
    """Flag a narrow coverage-count discrepancy, never rewrite or certify prose.

    Only the explicit phrase 'N [child agent] traces are missing/unavailable' is
    recognized. Other quantities and semantic/quoted scope remain unverified.
    """
    expected = len({link['child_agent_id'] for link in scope['capture_gaps']['missing_child_traces']})
    pattern = re.compile(r'\b(\d+)\s+child(?:[- ]agent|\s+agent)?\s+traces?\s+(?:are\s+)?(?:missing|unavailable)\b',re.I)
    checks = []
    def visit(value, path):
        if isinstance(value, str):
            for match in pattern.finditer(value):
                reported = int(match.group(1))
                checks.append({'check_type':'reported_missing_child_count','policy_version':VERSION,
                               'status':'passed' if reported == expected else 'needs_review',
                               'field':path,'quoted_text':match.group(0),'reported_value':reported,'scope_value':expected,
                               'basis':'Distinct missing child-agent identities in the immutable scope.',
                               'limitation':'Narrow literal count comparison; does not establish semantic scope or validate other prose quantities.'})
        elif isinstance(value,dict):
            for key,child in value.items():visit(child,path+'.'+key if path else key)
        elif isinstance(value,list):
            for index,child in enumerate(value):visit(child,path+'['+str(index)+']')
    visit(fields,'')
    return checks


def source_role(store, run, source_id):
    source = source_record(store, run, source_id)
    return record_role(source['record'], source['kind'])


def record_role(raw, kind=None):
    if kind == 'artifact':
        return 'artifact'
    from .session_scope import queued_instruction_metadata
    if queued_instruction_metadata(raw):
        return 'user_statement'
    blocks = content_blocks(raw)
    if any(b.get('type') == 'tool_result' for b in blocks) or isinstance(raw.get('toolUseResult'), dict):
        return 'tool_result'
    if any(b.get('type') == 'tool_use' for b in blocks):
        return 'tool_call'
    if raw.get('type') == 'system' or any(raw.get(k) for k in ('error', 'errorMessage', 'failureReason')):
        return 'system_status'
    if raw.get('type') == 'assistant':
        from .source_content import assistant_role
        return assistant_role(raw)
    return 'user_statement' if raw.get('type') == 'user' else 'other'


def inspected_reference(store, run, ref, delivered=None):
    delivered = delivered if delivered is not None else exposure(store, run['id'])['sources']
    text, sha, _, _ = projection(store, run, ref['source_id'], include_metadata=False)
    start, end = ref.get('start_char', 0), ref.get('end_char', len(text))
    if not 0 <= start < end <= len(text) or not text[start:end].strip():
        return False
    return any(s['source_id'] == ref['source_id'] and s['text_sha256'] == sha
               and any(left <= start and right >= end for left, right in s['delivered_ranges']) for s in delivered)


def reference_issues(store, run, refs, owner, delivered=None):
    return [{'code':'unread_cited_evidence', 'record_id':owner, 'source_id':r['source_id'],
             'reason':'The cited range, or complete source when no range was cited, has not been delivered.'}
            for r in refs if not inspected_reference(store, run, r, delivered)]


def has_primary_result(store, run, refs):
    return any(source_role(store, run, r['source_id']) in ('tool_result', 'artifact', 'system_status') for r in refs)


def outcome_issues(store, run, outcome):
    issues = reference_issues(store, run, outcome['references'], 'observed_outcome')
    if outcome['evidence_class'] == 'recorded_observation' and not has_primary_result(store, run, outcome['references']):
        issues.append({'code':'outcome_without_primary_result', 'record_id':'observed_outcome',
                       'reason':'A task outcome needs an inspected result or artifact. An assistant completion claim is a participant statement.'})
    if not outcome['references'] and not outcome['limitations']:
        issues.append({'code':'outcome_without_evidence_or_limit', 'record_id':'observed_outcome', 'reason':'Identify evidence or the gap preventing an observed result.'})
    return issues


def latest_inquiries(store, investigation_id):
    from .session_investigation import records
    values = records(store, investigation_id, 'inquiry')
    replaced = {v['inquiry'].get('revision_of') for v in values}
    return [v for v in values if v['id'] not in replaced]


def save_inquiry(store, investigation_id, inquiry):
    from .session_investigation import active_run, check_ids, put_record, record_by_id, validate_payload, validate_refs
    run = active_run(store, investigation_id)
    validate_payload(inquiry, INQUIRY)
    validate_refs(store, run, inquiry['references'])
    scope = get_scope(store, run)
    check_ids(inquiry['next_source_ids'], scope['event_ids'] + scope['artifact_ids'], 'next_source_ids')
    if inquiry.get('revision_of'):
        previous = record_by_id(store, investigation_id, 'inquiry', inquiry['revision_of'])
        if previous['inquiry']['kind'] != inquiry['kind']:
            raise AnalyzerError('An inquiry revision must retain its kind')
        if previous['id'] not in {q['id'] for q in latest_inquiries(store,investigation_id)}:
            raise AnalyzerError('An inquiry revision must name its current version')
        if inquiry['status'] != 'open':
            unread = [s for s in previous['inquiry']['next_source_ids'] if not inspected_reference(store,run,{'source_id':s})]
            if unread:
                raise AnalyzerError('Previously identified available sources remain unread: ' + ', '.join(unread))
    if inquiry['status'] != 'open' and inquiry['next_source_ids']:
        raise AnalyzerError('Available next sources remain unresolved; inspect them or retain the open inquiry')
    if inquiry['status'] == 'unavailable' and not inquiry['missing_evidence']:
        raise AnalyzerError('An unavailable inquiry needs the actual missing evidence')
    if inquiry['status'] in ('answered', 'disconfirmed') and not inquiry['references']:
        raise AnalyzerError('An answered inquiry needs references')
    body = {'inquiry':inquiry, 'basis':'caller_model_judgment', 'policy_version':VERSION}
    rid = put_record(store, run, 'inquiry', body)
    return {'id':rid, **body, 'review':get_diagnostic_status(store, investigation_id)}


def get_diagnostic_status(store, investigation_id):
    from .session_investigation import records
    run = get_run(store, investigation_id); delivered = exposure(store, investigation_id)['sources']
    inquiries = latest_inquiries(store, investigation_id); issues = []; suggested = set()
    if not any(v['inquiry']['kind'] == 'task_outcome' for v in inquiries):
        issues.append({'code':'task_outcome_not_investigated', 'reason':'Record the requested outcome and how it was investigated using save_inquiry.'})
    for value in inquiries:
        q = value['inquiry']
        if q['status'] == 'open':
            issues.append({'code':'open_material_inquiry', 'record_id':value['id'], 'question':q['question'], 'next_source_ids':q['next_source_ids']})
            suggested.update(q['next_source_ids'])
        else:
            issues += reference_issues(store, run, q['references'], value['id'], delivered)
            if q['kind'] == 'task_outcome' and q['status'] == 'answered' and entities(store, run, 'tool') and not has_primary_result(store, run, q['references']):
                issues.append({'code':'narrative_only_outcome_inquiry', 'record_id':value['id'], 'reason':'Inspect an original result before treating a tool-using task outcome as answered. If unavailable, state that gap.'})
    tools = entities(store, run, 'tool')
    from .session_review import active_versions, request_coverage
    if run.get('review_workflow'):
        coverage=request_coverage(store,run)
        if coverage['unread_requests']:
            issues.append({'code':'unmapped_main_requests','count':len(coverage['unread_requests']),
                           'reason':'Read the main-session requests to map intent and corrections before closing the declared session inquiry.',
                           'next_source_ids':[q['source_id'] for q in coverage['unread_requests'][:20]]})
            suggested.update(q['source_id'] for q in coverage['unread_requests'][:20])
    for saved in active_versions(records(store, investigation_id, 'incident'), 'incident'):
        incident = saved['incident']
        for claim in incident['claims']:
            issues += reference_issues(store, run, claim['references'], saved['id'], delivered)
            if claim.get('subject') == 'task_outcome' and claim['evidence_class'] == 'recorded_observation' and not has_primary_result(store, run, claim['references']):
                issues.append({'code':'narrative_only_outcome_claim', 'record_id':saved['id'], 'reason':'The task-outcome observation cites no original result or artifact; inspect one or preserve the claim as a participant report.'})
        issues += reference_issues(store, run, incident['task_references'] + incident['recovery_references'] + incident['counterevidence'], saved['id'], delivered)
        if incident['diagnosis'] == 'supported' or incident['resolution'] == 'recovered':
            members = set(incident['member_event_ids'])
            linked = [t for t in tools if t['id'] in incident['tool_ids'] or members.intersection(t['evidence'])]
            for tool in linked:
                for source_id in tool['evidence']:
                    if source_role(store, run, source_id) == 'tool_result' and not inspected_reference(store, run, {'source_id':source_id}, delivered):
                        issues.append({'code':'uninspected_incident_result', 'record_id':saved['id'], 'source_id':source_id, 'tool_id':tool['id'],
                                       'reason':'An original result linked to a supported/recovered incident remains uninspected.'})
    suggested.update(i['source_id'] for i in issues if 'source_id' in i)
    # De-duplicate repeated mechanical issues without changing authored records.
    unique = {str(sorted(i.items())):i for i in issues}
    from .session_failures import failure_coverage
    failures = failure_coverage(tools,records(store,investigation_id,'failure_explanation'))
    if run.get('review_workflow') and failures['not_investigated']:
        issues.append({'code':'unexplained_recorded_failures', 'count':failures['not_investigated'],
                       'reason':'Inspect counted attempts, or preserve insufficient-evidence explanations and their actual limits.'})
        unique = {str(sorted(i.items())):i for i in issues}
    from .session_requirements import current_map
    mapped=current_map(store,investigation_id)
    if run.get('review_workflow',{}).get('requirement_mapping_required') and not mapped:
        unique['requirement_map_missing']={'code':'requirement_map_missing','reason':'Save a scoped material requirement map. Unverified requirements and a partial inventory remain valid; request exposure alone is not fulfillment.'}
    return {'policy_version':VERSION, 'blocking_issues':list(unique.values()), 'suggested_source_ids':sorted(suggested),
            'requirement_map_id':mapped['id'] if mapped else None,
            'failure_explanations':failures,
            'active_inquiries':[{'id':v['id'], **v['inquiry']} for v in inquiries],
            'limitation':'Inspected evidence and closed questions are prerequisites, not independent proof of entailment, diagnosis or complete investigation.'}


def read_turn_evidence(store, investigation_id, turn_id, tool_offset=0, limit=3, max_chars=2000, allow_content=False):
    from .session_investigation import accounting
    run = get_run(store, investigation_id)
    bounded(tool_offset, 0, 10000000, 'tool_offset'); bounded(limit, 1, 4, 'limit'); bounded(max_chars, 1, 3000, 'max_chars')
    turns = {t['id']:t for t in accounting(store, run)['turns']}
    if turn_id not in turns:
        raise AnalyzerError('Turn is outside the immutable scope')
    turn = turns[turn_id]; all_tools = {t['id']:t for t in entities(store, run, 'tool')}
    selected = [all_tools[x] for x in turn['tool_ids']][tool_offset:tool_offset + limit]
    sources = list(dict.fromkeys([turn['request_event_id']] + [eid for t in selected for eid in t['evidence']]))
    pages = [dict(read_investigation_evidence(store, investigation_id, sid, max_chars=max_chars, allow_content=allow_content),
                  source_role=source_role(store, run, sid)) for sid in sources[:12]]
    return {'turn_id':turn_id, 'pages':pages,
            'tools':[{'id':t['id'], 'name':t['name'], 'outcome':t['outcome'],
                      'sources':[{'source_id':s, 'role':source_role(store, run, s)} for s in t['evidence']]} for t in selected],
            'remaining_source_ids':sources[12:],
            'next_tool_offset':tool_offset + len(selected) if tool_offset + len(selected) < len(turn['tool_ids']) else None,
            'total_tools':len(turn['tool_ids']), 'continuation':'Continue tool_offset for this turn; use each source fingerprint and next_start_char to reread truncated text. This is a selection, not the entire turn.'}
