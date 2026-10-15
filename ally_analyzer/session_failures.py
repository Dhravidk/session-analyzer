"""Attributed failure explanations; counts remain deterministic observations."""
from collections import defaultdict

from .session_contract import FAILURE_EXPLANATION
from .session_diagnostics import inspected_reference, reference_issues, source_role
from .session_investigation import (accounting, active_run, put_record, records,
                                    validate_payload, validate_refs)
from .session_patterns import RECORDED_FAILURE_OUTCOMES
from .session_scope import entities, exposure, get_run, log_access, scope_rows
from .util import AnalyzerError, bounded, timestamp

VERSION = 'failure-explanations-v2'


def recorded_failure(tool):
    return tool['requested'] and tool['outcome'] in RECORDED_FAILURE_OUTCOMES


def active_explanations(values):
    superseded = {v['explanation'].get('revision_of') for v in values}
    return {v['explanation']['tool_id']:v for v in values if v['id'] not in superseded}


def following_tools(tools, tool):
    """Recorded later calls by the same agent, not inferred retries or recovery."""
    end = timestamp(tool.get('result_timestamp') or tool.get('timestamp'))
    if end is None:
        return []
    agents = set(tool.get('agent_ids',[]))
    return sorted((t for t in tools if t['requested'] and t['id']!=tool['id']
                   and agents.intersection(t.get('agent_ids',[]))
                   and timestamp(t.get('timestamp')) is not None and timestamp(t['timestamp'])>end),
                  key=lambda t:(t['timestamp'],t['id']))


def failure_coverage(tools, values):
    active = active_explanations(values)
    ids = {t['id'] for t in tools if recorded_failure(t)}
    explained = sum(active[tid]['explanation']['status']=='explained' for tid in ids & active.keys())
    insufficient = sum(active[tid]['explanation']['status']=='insufficient_evidence' for tid in ids & active.keys())
    return {'recorded_failures':len(ids), 'explained':explained, 'insufficient_evidence':insufficient,
            'not_investigated':len(ids - active.keys()),
            'continuation':'get_recorded_failures',
            'limitation':'Saved explanations are model judgments. Their evidence prerequisites do not establish semantic accuracy or task harm.'}


def get_recorded_failures(store, investigation_id, limit=20, offset=0):
    bounded(limit, 1, 200, 'limit'); bounded(offset, 0, 10000000, 'offset')
    run = get_run(store, investigation_id)
    tools = entities(store, run, 'tool')
    values = records(store, investigation_id, 'failure_explanation')
    active = active_explanations(values)
    turns = accounting(store, run)['turns']
    memberships = defaultdict(list)
    for index, turn in enumerate(turns, 1):
        for tid in turn['tool_ids']:
            memberships[tid].append({'turn_id':turn['id'], 'turn_number':index, 'request_source_id':turn['request_event_id']})
    by_agent = defaultdict(list)
    for row in scope_rows(store, run):
        by_agent[row['agent_id']].append(row['id'])
    neighbors = {}
    for ids in by_agent.values():
        for index, sid in enumerate(ids):
            neighbors[sid] = ids[max(0,index-2):index] + ids[index+1:index+5]
    failures = sorted((t for t in tools if recorded_failure(t)), key=lambda t:(t.get('timestamp') or '', t['id']))
    page = []
    for tool in failures[offset:offset+limit]:
        roles = {sid:source_role(store,run,sid) for sid in tool['evidence']}
        context = list(dict.fromkeys(s for sid in tool['evidence'] for s in neighbors.get(sid,[]) if s not in roles))
        saved = active.get(tool['id'])
        following = following_tools(tools,tool)
        page.append({'tool_id':tool['id'], 'name':tool['name'], 'outcome':tool['outcome'], 'exit_code':tool.get('exit_code'),
                     'timestamp':tool.get('timestamp'), 'turns':memberships[tool['id']], 'evidence_roles':roles,
                     'next_tools':[{'tool_id':t['id'],'name':t['name'],'outcome':t['outcome'],
                                    'evidence_roles':{sid:source_role(store,run,sid) for sid in t['evidence']}} for t in following[:2]],
                     'later_tool_count':len(following),
                     'nearby_source_ids':context, 'explanation_id':saved['id'] if saved else None,
                     'explanation_status':saved['explanation']['status'] if saved else 'not_investigated'})
    rid = log_access(store,run,'recorded_failures',{'limit':limit,'offset':offset},
                     [{'source_id':sid,'access_type':'metadata'} for item in page for sid in item['evidence_roles']])
    return {'request_id':rid, 'items':page, 'total':len(failures),
            'next_offset':offset+len(page) if offset+len(page)<len(failures) else None,
            'coverage':failure_coverage(tools,values),
            'context_limit':'Nearby IDs are navigation aids, not complete recovery evidence. Follow later turns or search when needed.'}


def save_failure_explanation(store, investigation_id, explanation):
    run = active_run(store, investigation_id)
    validate_payload(explanation, FAILURE_EXPLANATION)
    tools = entities(store,run,'tool')
    tool = next((t for t in tools if t['id']==explanation['tool_id']), None)
    if tool is None or not recorded_failure(tool):
        raise AnalyzerError('Explanation must name a requested recorded failure inside this scope')
    values = records(store,investigation_id,'failure_explanation')
    current = active_explanations(values).get(tool['id'])
    # Retrying the exact same submission is idempotent. A changed explanation
    # needs an explicit linear revision; two competing active answers are invalid.
    if current and current['explanation']==explanation:
        return current
    if (current and explanation.get('revision_of')!=current['id']) or (not current and explanation.get('revision_of')):
        raise AnalyzerError('A changed explanation must revise the current explanation for the same tool')
    refs = explanation['references'] + explanation['recovery_references']
    validate_refs(store,run,refs)
    delivered = exposure(store,investigation_id)['sources']
    if reference_issues(store,run,refs,tool['id'],delivered):
        raise AnalyzerError('Read every cited range before saving the failure explanation')
    direct = {sid:source_role(store,run,sid) for sid in tool['evidence']}
    cited = {r['source_id'] for r in explanation['references']}
    original_roles = {role for sid,role in direct.items() if sid in cited}
    enough = 'tool_call' in original_roles and bool(original_roles & {'tool_result','system_status'})
    if explanation['status']=='explained' and not enough:
        raise AnalyzerError('An explained failure needs its own inspected tool input and original result references')
    incomplete = [sid for sid in direct if not inspected_reference(store,run,{'source_id':sid},delivered)]
    if (incomplete or explanation['status']=='insufficient_evidence' or explanation['resolution']=='unknown') and not explanation['limitations']:
        raise AnalyzerError('Identify the material evidence gap for incomplete evidence or unknown recovery')
    following = following_tools(tools,tool)
    all_cited = {r['source_id'] for r in refs}
    contextual_pair = any(t.get('result_present') and set(t['evidence']) <= all_cited for t in following)
    if explanation['status']=='explained' and any(t.get('result_present') for t in following):
        if not contextual_pair:
            raise AnalyzerError('Available follow-up results remain uninspected or uncited. Read and cite a relevant later tool input/result pair before marking explained; use get_recorded_failures next_tools to locate candidates. Otherwise save insufficient_evidence and identify the unfinished investigation.')
    if explanation['resolution'] in ('recovered','unresolved') and not any(r['source_id'] not in direct for r in explanation['recovery_references']):
        raise AnalyzerError('A recovered or unresolved classification needs inspected follow-up evidence')
    if explanation['resolution']=='recovered':
        # Temporal order + a recorded successful result is a prerequisite only.
        # Whether it repairs this particular failure remains Claude's judgment.
        times = {r['id']:timestamp(r['timestamp']) for r in scope_rows(store,run)}
        end = timestamp(tool.get('result_timestamp') or tool.get('timestamp'))
        recovery_ids = {r['source_id'] for r in explanation['recovery_references']}
        later_success = {sid for t in tools if t['outcome']=='success' and t['id']!=tool['id']
                         for sid in t['evidence'] if sid in recovery_ids and end is not None
                         and times.get(sid) is not None and times[sid]>end
                         and source_role(store,run,sid)=='tool_result'}
        if not later_success.intersection(r['source_id'] for r in explanation['recovery_references']):
            raise AnalyzerError('Recovered needs an inspected later successful tool result; a completion claim alone is insufficient')
    body = {'explanation':explanation, 'basis':'caller_model_judgment', 'policy_version':VERSION,
            'evidence_review':{'references_inspected':True, 'original_input_and_result_cited':enough,
                               'later_input_and_result_cited':contextual_pair,
                               'original_sources_not_fully_inspected':incomplete,
                               'limitation':'Reference, exposure and recovery prerequisites do not prove the explanation or its cause.'}}
    rid = put_record(store,run,'failure_explanation',body)
    return {'id':rid,**body}
