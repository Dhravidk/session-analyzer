"""Prerequisites for Claude-authored finding explanations; no prose generation."""
from .util import AnalyzerError


def incident_source_ids(incident):
    from .session_finding_links import incident_episodes
    ids=set(incident['member_event_ids'])
    for field in ('task_references','recovery_references','counterevidence'):
        ids.update(r['source_id'] for r in incident[field])
    ids.update(r['source_id'] for c in incident['claims'] for r in c['references'])
    ids.update(r['source_id'] for r in incident.get('pattern',{}).get('references',[]))
    for _,ep,_ in incident_episodes(incident):
        ids.update(episode_source_ids(ep))
    return ids


def episode_source_ids(episode):
    return ({r['source_id'] for r in episode['goal_references']} |
            {s for a in episode['attempts'] for s in a['event_ids']} |
            {r['source_id'] for v in episode['verification'] for r in v['references']})


def validate_reader_guide(store, run, incident):
    from .session_investigation import accounting, validate_refs
    from .session_requirements import inspected_refs
    from .session_scope import scope_rows
    guide=incident.get('reader_guide')
    if not guide:
        if run.get('review_workflow',{}).get('finding_reader_guides_version'):
            raise AnalyzerError('Save reader_guide: a short finding name, supported takeaway, and local events with decisive sources. The renderer cannot write these for you.')
        return
    allowed=incident_source_ids(incident)
    main={r['id'] for r in scope_rows(store,run) if r['agent_id']=='main'}
    turns=accounting(store,run)['turns']
    positions={sid:(n,j) for n,t in enumerate(turns) for j,sid in enumerate(t['event_ids']) if sid in main}
    episodes={e['key']:e['episode'] for e in incident.get('pattern',{}).get('episodes',[])}
    keys=set();last=None
    for entry in [guide]+guide['events']:
        refs=entry['references']
        if any(r['source_id'] not in allowed for r in refs):
            raise AnalyzerError('Reader-guide sources must be explicit incident members or citations')
        validate_refs(store,run,refs,require_text=True)
        inspected_refs(store,run,refs)
    for event in guide['events']:
        if event['key'] in keys:raise AnalyzerError('Reader-guide event keys must be distinct')
        keys.add(event['key'])
        refs={r['source_id'] for r in event['references']}
        if {event['anchor_source_id'],event['primary_source_id']}-refs:
            raise AnalyzerError('The event anchor and decisive source must both be cited in its references')
        position=positions.get(event['anchor_source_id'])
        if position is None:raise AnalyzerError('The event anchor must belong to an attributed main-session turn; cite the parent invocation for a child event')
        primary_position=positions.get(event['primary_source_id'])
        if primary_position is not None and primary_position[0]!=position[0]:
            raise AnalyzerError('A main-agent decisive source must belong to the same turn as its event anchor')
        if last is not None and position<last:raise AnalyzerError('Reader-guide events must follow recorded main-trajectory anchor order')
        last=position
        key=event.get('episode_key')
        if episodes:
            if key not in episodes:raise AnalyzerError('Each pattern event must name its saved episode_key')
            if event['primary_source_id'] not in episode_source_ids(episodes[key]):
                raise AnalyzerError('The decisive source must belong to the selected episode')
        elif key:raise AnalyzerError('An episode_key requires a saved pattern episode')
    if set(episodes)-{e.get('episode_key') for e in guide['events']}:
        raise AnalyzerError('Each saved pattern episode needs at least one reader-guide event')


def saved_source_explanation(ref, data, context=None):
    """Reuse only the citation or its latest same-owner, range-verified review."""
    if ref.get('explanation'):
        return ref['explanation'], None
    owner=(context or {}).get('owner_id')
    reviews=[r for r in data.get('review_checks',[]) if owner and r['check']['record_id']==owner]
    if not reviews:return None, None
    review=reviews[-1];source=data.get('sources',{}).get(ref['source_id'],{})
    for item,exact in zip(review['check'].get('evidence_checks',[]),review.get('verified_quote_ranges',[])):
        same=(item['reference']['source_id']==ref['source_id']==exact.get('source_id')
              and exact.get('text_sha256') and exact['text_sha256']==source.get('text_sha256'))
        inside=not ref.get('text_sha256') or (ref['text_sha256']==exact.get('text_sha256')
                and ref['start_char']<=exact['start_char'] and ref['end_char']>=exact['end_char'])
        if same and inside:return item['supports_or_contradicts'], review['check']['verdict']
    return None, None
