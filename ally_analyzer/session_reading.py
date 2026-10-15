"""Reading aids over saved judgments. No new diagnosis, ranking or prose rewrite."""
from .util import digest

REQUIREMENT_STATUS = {
    'supported_completed':'Supported as completed', 'contradicted':'Not met',
    'unverified':'Unverified', 'superseded':'Superseded', 'withdrawn':'Withdrawn',
}


def requirement_anchor(map_id, key):
    return 'requirement-' + digest(map_id + ':' + key)[:20]


def requirement_refs(item):
    return (item['intent_references'] + item['result_references'] + item['artifact_revision']['references']
            + [r for c in item['verification'] + item['intent_changes'] for r in c['references']]
            + item.get('intent_interpretation',{}).get('references',[])
            + item.get('next_action',{}).get('references',[]))


def related_turns(data, refs=(), event_ids=(), tool_ids=()):
    """Only explicit source/tool membership; no temporal or lexical matching."""
    source_ids = set(event_ids) | {r['source_id'] for r in refs}
    tids = set(tool_ids)
    turns = data.get('main_accounting', data['accounting'])['turns']
    return [t['id'] for t in turns if source_ids.intersection(t['event_ids']) or tids.intersection(t['tool_ids'])]


def current_review(data, record_id):
    checks = [r['check'] for r in data.get('review_checks', []) if r['check']['record_id'] == record_id]
    return checks[-1] if checks else None


def remaining_items(data):
    """Not-met work and unknown completion stay distinct, including review dissent."""
    result = []
    saved = data.get('requirement_map')
    for item in saved['requirement_map']['requirements'] if saved else []:
        if item['status'] not in ('contradicted', 'unverified'):
            continue
        refs = requirement_refs(item)
        entry={'kind':'requirement', 'id':requirement_anchor(saved['id'], item['key']),
                       'owner_id':saved['id'], 'title':item['description'], 'scope':item['scope'],
                       'status':REQUIREMENT_STATUS[item['status']], 'basis':item['status_basis'],
                       'limits':item['missing_evidence'], 'references':refs,
                       'checks':item['verification'], 'revision':item['artifact_revision'],
                       'interpretation':item.get('intent_interpretation'),
                       'turn_ids':related_turns(data, refs), 'review':current_review(data, saved['id'])}
        if item.get('next_action'):
            entry.update(next_action=item['next_action']['action'], next_action_check=item['next_action']['verification'],
                         action_limits=item['next_action']['limitations'])
        result.append(entry)
    for saved in data.get('incidents', []):
        item = saved['incident']
        if item['resolution'] not in ('unresolved', 'unknown'):
            continue
        refs = item['task_references'] + item['recovery_references'] + item['counterevidence']
        refs += [r for c in item['claims'] for r in c['references']]
        attribution = item.get('attribution', {})
        result.append({'kind':'finding', 'id':saved['id'], 'owner_id':saved['id'], 'title':item['title'],
                       'status':'Unresolved' if item['resolution']=='unresolved' else 'Outcome unknown',
                       'basis':item['membership_basis'], 'limits':item['open_questions'], 'references':refs,
                       'turn_ids':related_turns(data, refs, item['member_event_ids'], item['tool_ids']),
                       'next_action':attribution.get('immediate_next_action'),
                       'scope':attribution.get('component'), 'version':attribution.get('version'),
                       'review':current_review(data, saved['id'])})
    return result


def remaining_work_text(data):
    """A deterministic collation of saved text for the copy control, not a prompt."""
    items = remaining_items(data)
    if not items:
        return ''
    run = data['investigation']
    lines = [run.get('title') or 'Session '+run['root_session_id'],
             'Saved analysis: '+run['id'], 'Investigation: '+run['run_status'],
             'Not met and unverified are different states. This handoff copies saved judgments; it does not prescribe new work.']
    scope=data.get('scope',{})
    lines += ['Captured scope: '+str(scope.get('id') or run.get('scope_id') or 'Unavailable')]
    missing={g['child_agent_id'] for g in scope.get('capture_gaps',{}).get('missing_child_traces',[])}
    if missing: lines += ['Unavailable child traces: '+str(len(missing))]
    if run['run_status'] in ('partial','failed'):lines += [run.get('stop_reason') or 'No stop reason saved.']
    lines += ['Unresolved investigation question: '+s for s in run.get('unresolved_questions',[])]
    mapped = data.get('requirement_map', {}).get('requirement_map') if data.get('requirement_map') else None
    if mapped:
        lines += ['Requirement inventory: '+mapped['inventory_status'], *mapped['limitations']]
    else:
        lines += ['No requirement inventory saved.']
    reviewed=set()
    for item in items:
        lines += ['', item['status']+': '+item['title']]
        if item.get('scope'): lines += ['Scope: '+item['scope']]
        if item.get('version'): lines += ['Component version: '+item['version']]
        lines += [item['basis']]
        revision = item.get('revision')
        if revision: lines += ['Artifact revision: '+(revision.get('value') if revision['state']=='known' else revision['state'])]
        for check in item.get('checks', []):
            lines += ['Check: '+check['description'], ' / '.join([check['outcome'], 'scope '+check['scope_relation'], 'revision '+check['revision_relation']]), check['basis']]
        if item.get('next_action'): lines += ['Saved next action: '+item['next_action']]
        if item.get('next_action_check'): lines += ['Action verification: '+item['next_action_check'], *item['action_limits']]
        interpretation=item.get('interpretation')
        if interpretation:
            lines += ['Intent: '+interpretation['status'], interpretation['basis']]
            lines += ['Possible reading: '+s for s in interpretation['alternatives']]
        lines += ['Missing evidence: '+s for s in item['limits']]
        review = item.get('review')
        if review and review['verdict']!='supported' and item['owner_id'] not in reviewed:
            reviewed.add(item['owner_id'])
            lines += ['Claude review of '+('requirement map' if item['kind']=='requirement' else 'finding')+' '+item['owner_id']+': '+review['verdict'], review['assessment'], *review['remaining_uncertainty']]
            lines += [c['assessment'] for c in review.get('semantic_checks', []) if c['verdict']=='needs_revision']
        seen = set()
        for ref in item['references']:
            identity = (ref['source_id'], ref.get('start_char'), ref.get('end_char'))
            if identity in seen: continue
            seen.add(identity)
            location = ref['source_id']
            if ref.get('start_char') is not None: location += ':'+str(ref['start_char'])+'–'+str(ref.get('end_char', '?'))
            lines += ['Source: '+location+(' — '+ref['explanation'] if ref.get('explanation') else '')]
    return '\n'.join(lines)+'\n'
