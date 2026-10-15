"""Incident episode prerequisites and explicit-union resource accounting."""
from collections import Counter, defaultdict

from .session_scope import entities, get_scope, scope_rows, source_record
from .session_requirements import inspected_refs, verification_checks
from .session_resources import tool_measure
from .session_metrics import metric, token_metrics
from .util import AnalyzerError, timestamp

VERSION = 'recovery-episode-v1'


def validate_episode(store, run, incident):
    episode = incident.get('episode')
    if not episode: return None
    inspected_refs(store,run,episode['goal_references'])
    tools={t['id']:t for t in entities(store,run,'tool')}
    responses={r['id']:r for r in entities(store,run,'response')}
    keys=set(); used_tools=set(); used_events=set()
    for attempt in episode['attempts']:
        if attempt['key'] in keys: raise AnalyzerError('Episode attempt keys must be distinct')
        keys.add(attempt['key'])
        event_ids=set(attempt['event_ids']); tool_ids=set(attempt['tool_ids'])
        if event_ids - set(incident['member_event_ids']) or tool_ids - set(incident['tool_ids']):
            raise AnalyzerError('Attempt identities must be explicit members of this incident')
        if tool_ids & used_tools or event_ids & used_events:
            raise AnalyzerError('Keep attempts distinct: the same tool/event cannot be assigned to two attempts')
        used_tools |= tool_ids; used_events |= event_ids
        for tid in tool_ids:
            if not set(tools[tid]['evidence']) <= event_ids:
                raise AnalyzerError('An attempt must include the selected tool input and retained result identities')
            if tools[tid].get('step_id') in responses and tools[tid]['step_id'] not in attempt['response_ids']:
                raise AnalyzerError('Include the selected tool emission response explicitly; response usage cannot be silently omitted')
        for rid in attempt['response_ids']:
            if rid not in responses or not event_ids.intersection(responses[rid]['evidence']):
                raise AnalyzerError('An attempt response must have a recorded frame in that attempt; usage is not allocated from time intervals')
        inspected_refs(store,run,[{'source_id':sid} for sid in attempt['event_ids']])
    checks=verification_checks(store,run,episode['verification'])
    for check in episode['verification']:
        if any(ref['source_id'] not in used_events for ref in check['references'] if ref['source_id'] in get_scope(store,run)['event_ids']):
            raise AnalyzerError('Episode verification events must be included in an explicit attempt')
    if incident['resolution']=='recovered' and not any(c['adequate_for_completion'] for c in checks):
        raise AnalyzerError('Recovered needs verification of the same goal and relevant revision; a narrower passing retry alone is insufficient')
    if incident['resolution']=='recovered':
        rows=scope_rows(store,run)
        positions={r['id']:(i,r['agent_id']) for i,r in enumerate(rows)}
        times={r['id']:timestamp(r['timestamp']) for r in rows}
        connected=defaultdict(set)
        for link in get_scope(store,run)['delegation_links']:
            for parent in tools[link['tool_id']]['agent_ids']:
                connected[parent].add(link['child_agent_id']);connected[link['child_agent_id']].add(parent)
        def later(original, check):
            left,right=positions[original],positions[check]
            if left[1]==right[1]:return left[0]<right[0]
            reached={left[1]}; pending=[left[1]]
            while pending:
                for child in connected[pending.pop()]-reached:reached.add(child);pending.append(child)
            return right[1] in reached and times[original] is not None and times[check] is not None and times[check]>times[original]
        originals=[s for a in episode['attempts'] if a['role']=='original' for s in a['event_ids']]
        verified=[c for c,p in zip(episode['verification'],checks) if p['adequate_for_completion']]
        if not originals or not any(c.get('check_event_id') and all(later(s,c['check_event_id']) for s in originals) for c in verified):
            raise AnalyzerError('Recovered needs a later verification event. Cross-agent recovery also requires structural linkage and recorded ordering; otherwise preserve unknown.')
    # A repeated response may emit several tools. It remains one response in union totals.
    return {'verification':checks,'policy_version':VERSION,
            'limitation':'Claude justifies same-goal membership and interprets outcomes. The engine checks identities, chronology and evidence prerequisites only.'}


def validate_attribution(store, run, incident):
    value=incident.get('attribution')
    if not value: return None
    scope=get_scope(store,run)
    allowed=set(scope['agent_ids']) | {l['child_agent_id'] for l in scope['delegation_links']}
    if set(value['agent_ids'])-allowed: raise AnalyzerError('Fault attribution names an agent outside this session scope')
    for field in ('component_references','instruction_references','execution_references'):
        inspected_refs(store,run,value[field])
    unavailable=[a for a in value['agent_ids'] if not any(r['agent_id']==a for r in scope_rows(store,run))]
    shared=[v['id'] for kind in ('tool','response') for v in entities(store,run,kind)
            if len(v['agent_ids'])>1 and set(value['agent_ids']).intersection(v['agent_ids'])]
    reasons=[]
    if unavailable: reasons.append('missing_agent_trace')
    # Do not disqualify all attribution because an unrelated copied response exists.
    cited={r['source_id'] for r in value['execution_references']}
    cited_shared=[v['id'] for kind in ('tool','response') for v in entities(store,run,kind)
                  if v['id'] in shared and cited.intersection(v['evidence'])]
    if cited_shared: reasons.append('ambiguous_shared_execution_identity')
    plugin_category=value['category'] in ('defective_instruction','instruction_nonadherence')
    if plugin_category:
        if not value['instruction_references']: reasons.append('applicable_instruction_not_evidenced')
        if not value['component_references']: reasons.append('component_not_evidenced')
        if value['version_basis']!='historical': reasons.append('historical_component_version_not_established')
        if not value['execution_references']: reasons.append('historical_execution_not_evidenced')
        # A current/proposed snapshot alone cannot become proof of historical instructions.
        for ref in value['instruction_references']+value['component_references']:
            source=source_record(store,run,ref['source_id'])
            if source['kind']=='artifact' and source['metadata']['temporal_relation']!='historical':
                reasons.append('nonhistorical_snapshot')
        for ref in value['component_references']:
            source=source_record(store,run,ref['source_id'])
            if source['kind']=='artifact' and source['metadata'].get('version') and source['metadata']['version']!=value['version']:
                reasons.append('component_version_conflicts_with_admitted_snapshot')
    from .session_diagnostics import has_primary_result
    if value['support']=='established' and not has_primary_result(store,run,value['execution_references']):
        reasons.append('no_primary_execution_result')
    if value['category']=='insufficient_evidence' and value['support']=='established':
        raise AnalyzerError('Insufficient evidence cannot establish fault attribution')
    if value['support']=='established' and (reasons or not value['execution_references']):
        raise AnalyzerError('Fault attribution is not established: '+', '.join(sorted(set(reasons or ['execution_not_evidenced'])))+'. Preserve hypothesis/not_established and the evidence gap.')
    if value['support']!='established' and not value['missing_evidence']:
        raise AnalyzerError('Qualified attribution must identify missing evidence')
    return {'policy_version':VERSION,'qualifications':sorted(set(reasons)), 'unavailable_agent_ids':unavailable,
            'shared_execution_ids':cited_shared,
            'limitation':'Applicable historical versions and fault remain Claude judgments. Historical snapshot provenance is operator reported, not independent proof of what ran. Task incompletion does not establish plugin fault.'}


def episode_resources(store, run, saved_incidents):
    attempts=[a for v in saved_incidents for a in v['incident']['episode']['attempts']]
    counts={key:Counter(i for a in attempts for i in a[key]) for key in ('response_ids','tool_ids','event_ids')}
    selected={key:set(value) for key,value in counts.items()}
    responses=[r for r in entities(store,run,'response') if r['id'] in selected['response_ids']]
    tools=[t for t in entities(store,run,'tool') if t['id'] in selected['tool_ids']]
    rows=[r for r in scope_rows(store,run) if r['id'] in selected['event_ids']]
    metrics=token_metrics(responses)
    for key,value,ids in (('llm_calls',sum(r['eligible'] for r in responses),[e for r in responses for e in r['evidence']]),
                          ('tool_invocations',sum(t['requested'] for t in tools),[e for t in tools for e in t['evidence']])):
        metrics[key]=metric(key,value,'count',value,value,ids)
    metrics['recorded_tool_duration_ms']=tool_measure('recorded_tool_duration_ms',tools)
    intervals=[]
    for aid in sorted({r['agent_id'] for r in rows}):
        own=[r for r in rows if r['agent_id']==aid]
        known=[(timestamp(r['timestamp']),r['id']) for r in own if timestamp(r['timestamp']) is not None]
        first,last=(min(known),max(known)) if known else (None,None)
        span=last[0]-first[0] if len(known)>1 else None
        intervals.append({'agent_id':aid,'observed_elapsed_seconds':span,
                          'endpoint_source_ids':[first[1],last[1]] if first else [], 'known':len(known),'eligible':len(own),
                          'limitation':'First-to-last selected timestamp. Includes idle and unselected intervening work; not active recovery time. Do not add agent intervals.'})
    return {'formula':'recovery_episode_union','formula_version':VERSION,'incident_ids':[v['id'] for v in saved_incidents],
            'attempt_count':len(attempts),'selection':{k:sorted(v) for k,v in selected.items()},
            'overlapping_identities_counted_once':{k:sorted(i for i,n in c.items() if n>1) for k,c in counts.items()},
            'metrics':metrics,'observed_intervals':intervals,
            'unselected_tool_emissions_in_selected_responses':[t['id'] for t in entities(store,run,'tool') if t.get('step_id') in selected['response_ids'] and t['id'] not in selected['tool_ids']],
            'limitation':'Resources associated with explicitly justified attempts, not wasted work or avoidable overhead. Selected response usage can also serve other tool emissions; it is indivisible. Intervening work is excluded from counts. Overlapping episodes must be measured as a union, never by summing their reports.'}


def measure_recovery_episodes(store, investigation_id, incident_ids):
    from .session_investigation import active_run, records, put_record, check_ids
    from .session_review import active_versions
    run=active_run(store,investigation_id)
    available={v['id']:v for v in active_versions(records(store,investigation_id,'incident'),'incident') if v['incident'].get('episode')}
    check_ids(incident_ids,available,'incident_ids')
    if not incident_ids: raise AnalyzerError('Select at least one current episode')
    body=episode_resources(store,run,[available[i] for i in incident_ids])
    rid=put_record(store,run,'measurement',body)
    return {'id':rid,**body}
