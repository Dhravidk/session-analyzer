"""Finding navigation from explicit identities and associations, never prose inference."""
from .session_patterns import RECORDED_FAILURE_OUTCOMES
from .session_story import saved_source_explanation

ROLE_LABELS = {
    'failure':'Failure evidence', 'recovery':'Recovery evidence',
    'verification':'Verification evidence', 'corrective':'Corrective attempt',
    'original':'Original attempt', 'request':'Request context',
    'counterevidence':'Counterevidence', 'related':'Related evidence',
}


def incident_episodes(incident):
    if incident.get('episode'):
        return [(None, incident['episode'], incident['resolution'])]
    return [(e['key'], e['episode'], e['resolution']) for e in incident.get('pattern', {}).get('episodes', [])]


def relationship_label(roles):
    roles=set(roles)-{'related'}
    if not roles:return ROLE_LABELS['related']
    if {'failure','recovery'}<=roles:
        return ' · '.join(['Failure and recovery']+[text for role,text in ROLE_LABELS.items() if role in roles-{'failure','recovery'}])
    return ' · '.join(text for role,text in ROLE_LABELS.items() if role in roles)


def finding_links(data, saved):
    """Per-turn evidence links. Recovery roles do not establish successful recovery."""
    incident=saved['incident']; entries={}
    def add(ref,role='related',basis=None,context=None):
        sid=ref['source_id']
        entry=entries.setdefault(sid,{'ref':dict(ref),'roles':[],'bases':[], 'context':context})
        if role not in entry['roles']:entry['roles'].append(role)
        if basis and basis not in entry['bases']:entry['bases'].append(basis)
        # Prefer an existing exact citation/explanation, never generate one.
        if not entry['ref'].get('explanation') and ref.get('explanation'):
            entry['ref']=dict(ref);entry['context']=context
        elif 'start_char' not in entry['ref'] and 'start_char' in ref and not entry['ref'].get('explanation'):
            entry['ref']=dict(ref);entry['context']=context
    for field,role in (('task_references','request'),('recovery_references','recovery'),('counterevidence','counterevidence')):
        for ref in incident[field]:add(ref,role,'Saved '+field.replace('_',' '))
    for claim in incident['claims']:
        for ref in claim['references']:
            add(ref,context=claim['text'])
            entries[ref['source_id']]['claim_reference']=True
            entries[ref['source_id']].setdefault('claim_order',sum(e.get('claim_reference',False) for e in entries.values()))
    for relation in incident.get('evidence_links',[]):
        for ref in relation['references']:add(ref,relation['role'],'Saved evidence relationship',relation['basis'])
    for ref in incident.get('pattern',{}).get('references',[]):add(ref,context=incident['pattern']['membership_basis'])
    for event in incident.get('reader_guide',{}).get('events',[]):
        for ref in event['references']:add(ref,context=event['explanation'])
    for _,episode,_ in incident_episodes(incident):
        for ref in episode['goal_references']:add(ref,'request','Saved episode goal reference')
        for attempt in episode['attempts']:
            for sid in attempt['event_ids']:add({'source_id':sid},attempt['role'],'Saved episode attempt',attempt['same_goal_basis'])
        for check in episode['verification']:
            for ref in check['references']:add(ref,'verification','Saved episode verification',check['basis'])
    for sid in incident['member_event_ids']:add({'source_id':sid})
    for tool in data.get('tools',[]):
        if tool['id'] in incident['tool_ids']:
            for sid in tool['evidence']:add({'source_id':sid})
        if tool['outcome'] in RECORDED_FAILURE_OUTCOMES:
            for sid in tool['evidence']:
                if sid in entries and data.get('sources',{}).get(sid,{}).get('role')=='tool_result':
                    add({'source_id':sid},'failure','Recorded tool outcome: '+tool['outcome'])
    result={}
    for turn in data.get('main_accounting',data['accounting'])['turns']:
        selected=[entries[sid] for sid in turn['event_ids'] if sid in entries]
        if not selected:continue
        # Explicit attempt/result roles first, then claim-cited results before
        # request context. Citation priority does not classify a result's role.
        order={role:n for n,role in enumerate(ROLE_LABELS)}
        def priority(entry):
            result=data.get('sources',{}).get(entry['ref']['source_id'],{}).get('role')=='tool_result'
            rank=min(order[r] for r in entry['roles'])
            if result and entry.get('claim_reference') and 'counterevidence' not in entry['roles']:rank=min(rank,4.5)
            elif result and 'counterevidence' in entry['roles']:rank=min(rank,4.75)
            explanation,verdict=saved_source_explanation(entry['ref'],data,{'owner_id':saved['id']})
            if result and entry.get('claim_reference') and explanation and 'counterevidence' not in entry['roles']:
                # Prefer the author's explained claim evidence in saved order.
                # A peripheral failed grep must not outrank the cited run result.
                return -1,entry['claim_order'],False
            return rank,not bool(explanation),not result
        selected=sorted(selected,key=priority)
        for entry in selected:entry['label']=relationship_label(entry['roles'])
        events=[e for e in incident.get('reader_guide',{}).get('events',[]) if e['anchor_source_id'] in turn['event_ids']]
        result[turn['id']]={'label':relationship_label(r for e in selected for r in e['roles']), 'evidence':selected,'events':events}
    return result
