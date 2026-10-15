"""Identity-based resource views. No waste, compaction or causality inference."""
from collections import defaultdict
import re

from .session_metrics import metric, token_metrics
from .session_scope import entities, get_run, get_scope, log_access, projection, scope_rows
from .util import AnalyzerError, bounded, integer, digest

VERSION = 'resource-evidence-v2'
DEFINITIONS = {
    'peak_input_tokens':'Largest total input among eligible recorded responses. Missing inputs leave the population peak unknown; known maximum is an observed lower bound.',
    'cache_read_share':'Sum of cache reads / sum of total input for the SAME eligible responses with all input components known. Input already includes reads and writes. Missing responses are excluded from both known-population sums, not silently treated as zero.',
    'captured_tool_result_bytes':'UTF-8 bytes of captured result content (canonical JSON for structured content), once per reconciled tool identity. Not model-input tokens or proof of full original output.',
    'recorded_tool_duration_ms':'Sum of explicitly recorded, non-conflicting tool execution durations. May overlap; not elapsed wall time, active time, or avoidable overhead.',
    'input_change_tokens':'Second response total input minus first response total input in the same recorded agent trajectory. Does not establish compaction or its effect.',
    'cache_read_share_change_pp':'Second response cache-read share minus first response share, multiplied by 100. Each share uses the same response for numerator and denominator. Percentage points, not relative percent.',
    'recorded_compaction_duration_ms':'Native compactMetadata.durationMs at exactly one recorded compaction boundary. Not an inferred timestamp gap.'}


def response_measure(formula, responses):
    eligible = [r for r in responses if r['eligible']]
    if formula == 'peak_input_tokens':
        known = [r for r in eligible if r['tokens'].get('total_input_tokens') is not None]
        maximum = max((r['tokens']['total_input_tokens'] for r in known), default=None)
        result = metric(formula, maximum if known and len(known)==len(eligible) else None,
                        'tokens', len(known), len(eligible), [s for r in known for s in r['evidence']], known_subtotal=None)
        result.update(known_maximum=maximum, peak_response_ids=[r['id'] for r in known if r['tokens']['total_input_tokens']==maximum])
    elif formula == 'cache_read_share':
        known = [r for r in eligible if all(r['tokens'].get(k) is not None for k in ('total_input_tokens','input_tokens','cache_creation_input_tokens','cache_read_input_tokens'))]
        numerator = sum(r['tokens']['cache_read_input_tokens'] for r in known)
        denominator = sum(r['tokens']['total_input_tokens'] for r in known)
        share = numerator/denominator if denominator else None
        result = metric(formula, share if len(known)==len(eligible) else None, 'ratio', len(known), len(eligible),
                        [s for r in known for s in r['evidence']], known_subtotal=None)
        result.update(known_population_ratio=share, numerator=numerator, denominator=denominator,
                      numerator_response_ids=[r['id'] for r in known], denominator_response_ids=[r['id'] for r in known])
    else: raise AnalyzerError('Unknown response resource formula')
    result.update(definition=DEFINITIONS[formula], definition_id=formula+':'+VERSION,
                  eligible_response_ids=[r['id'] for r in eligible], known_response_ids=[r['id'] for r in known],
                  unknown_response_ids=[r['id'] for r in eligible if r not in known])
    return result


def tool_measure(formula, tools):
    requested = [t for t in tools if t['requested']]
    field = {'captured_tool_result_bytes':'result_bytes','recorded_tool_duration_ms':'recorded_duration_ms'}[formula]
    valid = [t for t in requested if integer(t.get(field)) and not t['warnings']]
    subtotal = sum(t[field] for t in valid)
    result = metric(formula, subtotal if valid and len(valid)==len(requested) else None,
                    'bytes' if formula=='captured_tool_result_bytes' else 'ms', len(valid), len(requested),
                    [s for t in valid for s in t['evidence']], known_subtotal=subtotal)
    result.update(definition=DEFINITIONS[formula], definition_id=formula+':'+VERSION,
                  eligible_tool_ids=[t['id'] for t in requested], known_tool_ids=[t['id'] for t in valid])
    return result


def select_agent(store, run, agent_id, turn_id=None):
    from .session_investigation import accounting
    scope = get_scope(store, run)
    available = set(scope['agent_ids']) | {x['child_agent_id'] for x in scope['delegation_links']}
    if agent_id not in available: raise AnalyzerError('Agent is outside this session scope')
    rows = scope_rows(store, run)
    selected = {r['id'] for r in rows if r['agent_id']==agent_id}
    if turn_id:
        turn = next((t for t in accounting(store,run)['turns'] if t['id']==turn_id), None)
        if not turn: raise AnalyzerError('Turn is outside this session scope')
        selected &= set(turn['event_ids'])
    return rows, selected


def context_timeline(store, run, agent_id='main', turn_id=None):
    from .session_investigation import accounting
    rows, selected = select_agent(store, run, agent_id, turn_id)
    positions = {r['id']:i for i,r in enumerate(rows)}
    all_responses = entities(store, run, 'response')
    # Copied histories cannot be charged twice or assigned confidently to an actor.
    rs = [r for r in all_responses if r['eligible'] and r['agent_ids']==[agent_id]]
    rs.sort(key=lambda r:min(positions[e] for e in r['evidence']))
    points = []; previous = None
    for r in rs:
        if not selected.intersection(r['evidence']): continue
        share = response_measure('cache_read_share',[r])
        points.append({'kind':'response', 'id':r['id'], 'source_ids':r['evidence'], 'timestamp':r.get('timestamp'),
                       'models':r.get('models',[]), 'tokens':r['tokens'], 'cache_read_share':share,
                       'order':min(positions[e] for e in r['evidence'])})
    for r in rs:
        if previous and selected.intersection(r['evidence']) and len(previous.get('models',[]))==len(r.get('models',[]))==1 and previous['models']!=r['models']:
            points.append({'kind':'model_change', 'id':'model_'+r['id'], 'from':previous['models'], 'to':r['models'],
                           'source_ids':previous['evidence']+r['evidence'], 'order':min(positions[e] for e in r['evidence'])})
        previous = r
    for turn in accounting(store, run)['turns']:
        if turn['request_event_id'] in selected:
            points.append({'kind':'turn_boundary', 'id':turn['id'], 'source_ids':[turn['request_event_id']],
                           'order':positions[turn['request_event_id']]})
    for event in entities(store, run, 'lifecycle'):
        if event['agent_id']!=agent_id or event['id'] not in selected or 'compaction' not in event: continue
        at = positions[event['id']]
        before = [r for r in rs if max(positions[e] for e in r['evidence']) < at]
        after = [r for r in rs if min(positions[e] for e in r['evidence']) > at]
        pre, post = (before[-1] if before else None), (after[0] if after else None)
        def snapshot(r):
            return {'response_id':r['id'], 'source_ids':r['evidence'], 'tokens':r['tokens'],
                    'cache_read_share':response_measure('cache_read_share',[r])['value']} if r else None
        pre, post = snapshot(pre), snapshot(post)
        md = event['compaction']
        delta = (post['cache_read_share']-pre['cache_read_share'])*100 if pre and post and pre['cache_read_share'] is not None and post['cache_read_share'] is not None else None
        points.append({'kind':'recorded_compaction', 'id':event['id'], 'source_ids':event['evidence'], 'order':at,
                       'timestamp':event.get('timestamp'), 'metadata':md,
                       'recorded_duration_ms':md.get('durationMs') if integer(md.get('durationMs')) else None,
                       'before':pre, 'after':post, 'cache_read_percentage_point_change':delta,
                       'limitation':'Nearest eligible responses in this agent trajectory, possibly outside the selected turn. Metadata pre/post counts and observed response inputs are separate populations. Temporal adjacency is not causality.'})
    chosen = [r for r in rs if selected.intersection(r['evidence'])]
    shared = [r['id'] for r in all_responses if agent_id in r['agent_ids'] and len(r['agent_ids'])>1 and selected.intersection(r['evidence'])]
    points.sort(key=lambda p:(p['order'],p['kind']))
    return {'version':VERSION, 'agent_id':agent_id, 'turn_id':turn_id, 'items':points,
            'peak_input':response_measure('peak_input_tokens',chosen), 'cache_read_share':response_measure('cache_read_share',chosen),
            'coverage':{'captured_event_count':len(selected), 'eligible_response_count':len(chosen), 'shared_response_ids_excluded':shared,
                        'recorded_compaction_count':sum(p['kind']=='recorded_compaction' for p in points)},
            'limitation':'No compaction inferred from input drops; no cache eviction or lost instruction inferred from cache share. Read before/after evidence. Cache reads/writes are included in input; thinking is included in output. Spans are not execution durations.'}


def get_context_timeline(store, investigation_id, agent_id='main', turn_id=None, limit=20, offset=0):
    bounded(limit,1,200,'limit'); bounded(offset,0,10000000,'offset')
    run=get_run(store,investigation_id); data=context_timeline(store,run,agent_id,turn_id)
    items=data['items']; page=items[offset:offset+limit]
    rid=log_access(store,run,'context_timeline',{'agent_id':agent_id,'turn_id':turn_id,'offset':offset,'limit':limit},
                   [{'source_id':sid,'access_type':'metadata'} for p in page for sid in p['source_ids']])
    return {**data, 'peak_input':compact_population(data['peak_input']), 'cache_read_share':compact_population(data['cache_read_share']),
            'request_id':rid,'items':page,'total':len(items),'next_offset':offset+len(page) if offset+len(page)<len(items) else None,
            'population_id':digest([run['scope_id'],agent_id,turn_id,data['peak_input']['eligible_response_ids']]),
            'identity_continuation':'Page this timeline for each response identity and source. Use measure_selection for an exact saved population measurement; missing/shared identities are explicit in coverage.'}


def compact_population(value):
    """Default navigation pages must not repeat the whole identity population."""
    result={k:v for k,v in value.items() if not k.endswith('_ids')}
    result['identity_counts']={k:len(v) for k,v in value.items() if k.endswith('_ids')}
    result['identity_previews']={k:v[:5] for k,v in value.items() if k.endswith('_ids')}
    return result


def boundary_measure(store, run, formula, responses, event_ids):
    if formula=='recorded_compaction_duration_ms':
        matches=[e for e in entities(store,run,'lifecycle') if e['id'] in event_ids and 'compaction' in e]
        if len(event_ids)!=1 or len(matches)!=1:raise AnalyzerError('Select exactly one recorded compaction event')
        value=matches[0]['compaction'].get('durationMs');value=value if integer(value) else None
        result=metric(formula,value,'ms',int(value is not None),1,event_ids)
    else:
        if len(responses)!=2 or any(not r['eligible'] for r in responses):raise AnalyzerError('Select exactly two ordered eligible response identities')
        if len(responses[0]['agent_ids'])!=1 or responses[0]['agent_ids']!=responses[1]['agent_ids']:
            raise AnalyzerError('A response change needs two unambiguous responses in the same agent trajectory')
        pos={r['id']:i for i,r in enumerate(scope_rows(store,run))}
        if max(pos[e] for e in responses[0]['evidence'])>=min(pos[e] for e in responses[1]['evidence']):
            raise AnalyzerError('Select response identities in recorded before/after order')
        values=[r['tokens'].get('total_input_tokens') for r in responses] if formula=='input_change_tokens' else [response_measure('cache_read_share',[r])['value'] for r in responses]
        known=sum(v is not None for v in values);value=(values[1]-values[0])*(100 if formula=='cache_read_share_change_pp' else 1) if known==2 else None
        result=metric(formula,value,'percentage_points' if formula=='cache_read_share_change_pp' else 'tokens',known,2,[e for r in responses for e in r['evidence']])
        result.update(before_response_id=responses[0]['id'],after_response_id=responses[1]['id'],before_value=values[0],after_value=values[1])
    return {**result,'definition':DEFINITIONS[formula],'definition_id':formula+':'+VERSION}


TRUNCATION_MARKERS = re.compile(r'(?i)(?:output (?:was |has been )?truncated|\[truncated\]|<persisted-output>|full output saved|exceeds maximum allowed tokens)')


def tool_output_index(store, run, agent_id='main', turn_id=None, inspect_markers=False):
    rows, selected = select_agent(store,run,agent_id,turn_id)
    tools = [t for t in entities(store,run,'tool') if t['requested'] and t['agent_ids']==[agent_id] and selected.intersection(t['evidence'])]
    inputs, results = defaultdict(list), defaultdict(list)
    for t in tools:
        if t.get('input_fingerprint'): inputs[t['name']+':'+t['input_fingerprint']].append(t['id'])
        if t.get('result_fingerprint'): results[t['result_fingerprint']].append(t['id'])
    items=[]
    for t in tools:
        markers=[]
        if inspect_markers:
            from .session_diagnostics import source_role
            for sid in t['evidence']:
                if source_role(store,run,sid)!='tool_result': continue
                text,_,_,_=projection(store,run,sid,include_metadata=False)
                if TRUNCATION_MARKERS.search(text): markers.append(sid)
        items.append({'tool_id':t['id'], 'name':t['name'], 'captured_result_bytes':t.get('result_bytes'),
                      'source_ids':t['evidence'], 'input_source_id':t.get('evidence_id'),
                      'input_group_id':t['name']+':'+t['input_fingerprint'] if t.get('input_fingerprint') else None,
                      'result_group_id':t.get('result_fingerprint'),
                      'same_input_count':len(inputs.get(t['name']+':'+str(t.get('input_fingerprint')),[])),
                      'same_result_count':len(results.get(t.get('result_fingerprint'),[])),
                      'truncation_marker_source_ids':markers, 'truncation_detection':'literal_marker_candidate_only' if inspect_markers else 'not_run',
                      'warnings':t['warnings']})
    items.sort(key=lambda t: (-(t['captured_result_bytes'] if t['captured_result_bytes'] is not None else -1), t['tool_id']))
    return {'version':VERSION, 'agent_id':agent_id,'turn_id':turn_id,'items':items,
            'input_groups':dict(inputs),'result_groups':dict(results),
            'captured_bytes':tool_measure('captured_tool_result_bytes',tools),
            'limitation':'Captured bytes are not actual model-input tokens. Repeated input/result identities and literal truncation markers are investigation candidates, not waste findings. A marker can be quoted text. Full retained records are paged through the controlled source reader; output never captured cannot be recovered here.'}


def get_tool_output_index(store, investigation_id, agent_id='main', turn_id=None, inspect_markers=False, limit=20, offset=0, allow_content=False, same_input_as=None, same_result_as=None):
    if inspect_markers:
        from .trajectory import require_content
        require_content(allow_content)
    bounded(limit,1,200,'limit'); bounded(offset,0,10000000,'offset')
    run=get_run(store,investigation_id); data=tool_output_index(store,run,agent_id,turn_id,inspect_markers)
    items=data['items']
    if same_input_as and same_result_as:raise AnalyzerError('Select one repeated-input or repeated-result group at a time')
    if same_input_as or same_result_as:
        anchor=next((i for i in items if i['tool_id']==(same_input_as or same_result_as)),None)
        if not anchor:raise AnalyzerError('Repeated-output anchor is outside this agent/turn selection')
        key='input_group_id' if same_input_as else 'result_group_id'
        if not anchor[key]:raise AnalyzerError('The selected tool has no captured group identity')
        items=[i for i in items if i[key]==anchor[key]]
    page=items[offset:offset+limit]
    rid=log_access(store,run,'tool_output_index',{'agent_id':agent_id,'turn_id':turn_id,'inspect_markers':inspect_markers,'offset':offset,'limit':limit,'same_input_as':same_input_as,'same_result_as':same_result_as},
                   [{'source_id':sid,'access_type':'metadata'} for p in page for sid in p['source_ids']])
    return {**{k:v for k,v in data.items() if k not in ('input_groups','result_groups')},
            'captured_bytes':compact_population(data['captured_bytes']),
            'request_id':rid,'items':page,'total':len(items),'next_offset':offset+len(page) if offset+len(page)<len(items) else None,
            'population':'Captured bytes describe the selected agent/turn population before an optional repeated-group filter.',
            'group_filter':{'same_input_as':same_input_as,'same_result_as':same_result_as},
            'identity_continuation':'Page the index with same_input_as or same_result_as set to a listed tool ID to inspect its whole group without repeating every group identity on every row.'}
