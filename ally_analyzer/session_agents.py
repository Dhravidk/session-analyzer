"""Separate main/child views without changing canonical accounting or scope."""
from collections import defaultdict

from .normalize import content_blocks
from .session_metrics import metric, token_metrics
from .session_patterns import RECORDED_FAILURE_OUTCOMES, turn_patterns
from .session_scope import entities, get_run, get_scope, log_access, scope_rows
from .util import AnalyzerError, bounded, strict_json, timestamp


def actor_metrics(rows, responses, tools):
    metrics = token_metrics(responses)
    eligible = [r for r in responses if r['eligible']]
    requested = [t for t in tools if t['requested']]
    metrics['llm_calls'] = metric('llm_calls',len(eligible),'count',len(eligible),len(eligible),[e for r in eligible for e in r['evidence']])
    metrics['tool_invocations'] = metric('tool_invocations',len(requested),'count',len(requested),len(requested),[e for t in requested for e in t['evidence']])
    times = [(timestamp(r['timestamp']),r['id']) for r in rows if timestamp(r['timestamp']) is not None]
    first,last = (min(times),max(times)) if times else (None,None)
    span = last[0]-first[0] if first and len(times)>1 else None
    metrics['session_duration_minutes'] = metric('session_duration_minutes',span/60 if span is not None else None,'minutes',len(times),len(rows),[first[1],last[1]] if first else [])
    metrics['session_duration_minutes']['definition'] = 'First to last recorded timestamp for this agent only. Includes idle intervals; not active time. Concurrent agent spans must not be added.'
    return metrics


def build_agent_views(store, run, accounting):
    scope = get_scope(store,run); rows = scope_rows(store,run)
    responses,tools = entities(store,run,'response'),entities(store,run,'tool')
    links = scope['delegation_links']; children = defaultdict(set)
    for link in links: children[link['tool_id']].add(link['child_agent_id'])
    delegations = [{'tool_id':t['id'], 'name':t['name'], 'parent_agent_ids':t['agent_ids'],
                    'child_agent_ids':sorted(children[t['id']]), 'outcome':t['outcome'],
                    'delegation_status':t.get('delegation_status'), 'evidence_ids':t['evidence'],
                    'invocation_source_id':t.get('evidence_id'),
                    'reported_child_summary':t.get('child_summary'), 'reported_summary_additive':False,
                    'link_evidence':[x for x in links if x['tool_id']==t['id']]}
                   for t in sorted(tools,key=lambda t:(t.get('timestamp') or '',t['id']))
                   if t['requested'] and (t['name'] in ('Agent','Task') or t['id'] in children)]
    agents = {}
    metadata = {a['agent_id']:a for a in store.items(run['analysis_id'],'agent',run['root_session_id'])}
    for aid in sorted(set(scope['agent_ids']) | {a for ids in children.values() for a in ids}):
        own_rows = [r for r in rows if r['agent_id']==aid]
        # Copied provider/tool identities shared by agents are not assigned twice.
        own_rs = [r for r in responses if r['agent_ids']==[aid]]
        own_ts = [t for t in tools if t['agent_ids']==[aid]]
        available = bool(own_rows)
        assistant = [r['id'] for r in own_rows if r['kind']=='assistant' and
                     any(b.get('type')=='text' for b in content_blocks(strict_json(r['raw'])))]
        agents[aid] = {'agent_id':aid,'role':metadata.get(aid,{}).get('role','unknown'),
                       'trace_status':'captured' if available else 'unavailable',
                       'event_ids':[r['id'] for r in own_rows], 'response_ids':[r['id'] for r in own_rs], 'tool_ids':[t['id'] for t in own_ts],
                       'metrics':actor_metrics(own_rows,own_rs,own_ts) if available else None,
                       'failure_tool_ids':[t['id'] for t in own_ts if t['requested'] and t['outcome'] in RECORDED_FAILURE_OUTCOMES],
                       'last_message_source_id':assistant[-1] if assistant else None,
                       'invocation_ids':[d['tool_id'] for d in delegations if aid in d['parent_agent_ids']],
                       'parent_invocation_ids':[d['tool_id'] for d in delegations if aid in d['child_agent_ids']],
                       'shared_response_ids':[r['id'] for r in responses if aid in r['agent_ids'] and len(r['agent_ids'])>1],
                       'shared_tool_ids':[t['id'] for t in tools if aid in t['agent_ids'] and len(t['agent_ids'])>1],
                       'capture_limit':'Captured records do not establish complete execution. Shared identities are excluded from individual agent metrics; combined accounting retains them once.'}
    main = agents['main']; main_ids=set(main['event_ids']); main_rs=set(main['response_ids']); main_ts=set(main['tool_ids'])
    main_turns=[]
    for turn in accounting['turns']:
        rs=[r for r in responses if r['id'] in main_rs and r['id'] in turn['response_ids']]
        ts=[t for t in tools if t['id'] in main_ts and t['id'] in turn['tool_ids']]
        selected=[r for r in rows if r['id'] in main_ids and r['id'] in turn['event_ids']]
        metrics=actor_metrics(selected,rs,ts)
        metrics['turn_duration_seconds']=turn['metrics']['turn_duration_seconds']
        span=metrics.pop('session_duration_minutes')
        start=next((timestamp(r['timestamp']) for r in selected if r['id']==turn['request_event_id']),None)
        times=[timestamp(r['timestamp']) for r in selected if timestamp(r['timestamp']) is not None]
        seconds=max(times)-start if times and start is not None else None
        metrics['observed_turn_span_seconds']=metric('observed_turn_span_seconds',seconds,
                                                   'seconds',span['known'],span['eligible'],span['source_ids'])
        main_turns.append({**turn,'metrics':metrics,'event_ids':[r['id'] for r in selected],
                           'response_ids':[r['id'] for r in rs],'tool_ids':[t['id'] for t in ts]})
    main_metrics={**main['metrics'],**{key:accounting['session'][key] for key in ('user_turns','task_requests','human_origin_turns') if key in accounting['session']}}
    patterns=turn_patterns(main_turns,[t for t in tools if t['id'] in main_ts])
    for pattern in patterns['rows']:
        pattern['member_tool_ids']=[tid for t in main_turns if t['id'] in pattern['member_turn_ids'] for tid in t['tool_ids']]
    return {'agents':agents,'delegations':delegations,
            'main_accounting':{**accounting,'session':main_metrics,'turns':main_turns,'population':'Main agent only; children are available through their invocations.'},
            'main_turn_patterns':patterns}


def get_subagent_details(store, investigation_id, tool_id, agent_id=None, limit=20, offset=0):
    from .session_investigation import accounting
    bounded(limit,1,200,'limit'); bounded(offset,0,10000000,'offset')
    run=get_run(store,investigation_id); view=build_agent_views(store,run,accounting(store,run))
    invocation=next((d for d in view['delegations'] if d['tool_id']==tool_id),None)
    if not invocation: raise AnalyzerError('Subagent invocation is outside the admitted scope')
    aids=invocation['child_agent_ids']
    if agent_id:
        if agent_id not in aids: raise AnalyzerError('Agent is not linked to this invocation')
        aids=[agent_id]
    selected=[view['agents'][aid] for aid in aids]
    allowed={sid for a in selected for sid in a['event_ids']}
    rows=[{k:r[k] for k in ('id','kind','agent_id','timestamp')} for r in scope_rows(store,run) if r['id'] in allowed]
    page=rows[offset:offset+limit]
    rid=log_access(store,run,'subagent_details',{'tool_id':tool_id,'agent_id':agent_id,'offset':offset,'limit':limit},
                   [{'source_id':r['id'],'access_type':'metadata'} for r in page])
    compact=[]
    for a in selected:
        item={k:v for k,v in a.items() if k not in ('event_ids','response_ids','tool_ids','metrics')}
        item.update(event_count=len(a['event_ids']),metrics={k:{n:v for n,v in m.items() if n!='source_ids'} for k,m in (a['metrics'] or {}).items()} if a['metrics'] else None)
        compact.append(item)
    return {'request_id':rid,'invocation':invocation,'agents':compact,'events':page,'total_events':len(rows),
            'next_offset':offset+len(page) if offset+len(page)<len(rows) else None,
            'continuation':'Read these source IDs with read_investigation_evidence or read_investigation_batch; follow nested invocation_ids with get_subagent_details.',
            'limitation':'A reported child summary is not a captured child trace and is never added to observed usage.'}
