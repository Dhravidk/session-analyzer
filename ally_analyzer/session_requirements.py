"""Versioned intent-to-result maps. Authorship is separate from prerequisites."""
from .session_scope import exposure, get_run, scope_rows
from .util import AnalyzerError

VERSION = 'requirement-evidence-v3'


def delivered_response_check(store, run, item):
    """Check retained response content; task relevance remains Claude's judgment."""
    from .normalize import content_blocks
    from .session_scope import source_record
    from .session_diagnostics import source_role
    evidence = item.get('delivered_response_evidence')
    if not evidence:
        return False
    inspected_refs(store, run, evidence['references'])
    def identity(ref): return {k:ref[k] for k in ('source_id','text_sha256','start_char','end_char') if k in ref}
    if any(identity(ref) not in [identity(result) for result in item['result_references']] for ref in evidence['references']):
        raise AnalyzerError('Delivered response evidence must also appear in result_references with the same ranges')
    for ref in evidence['references']:
        raw = source_record(store, run, ref['source_id'])['record']
        if source_role(store, run, ref['source_id']) != 'assistant_statement' or not any(
                b.get('type') == 'text' and isinstance(b.get('text'), str) and b['text'].strip()
                for b in content_blocks(raw)):
            raise AnalyzerError('Delivered response evidence needs retained assistant text, not a tool call, request or empty response')
    return True


def inspected_refs(store, run, refs, reader_facing=True):
    from .session_investigation import validate_refs
    from .session_diagnostics import inspected_reference
    validate_refs(store, run, refs, reader_facing=reader_facing)
    delivered = exposure(store, run['id'])['sources']
    if any(not inspected_reference(store, run, ref, delivered) for ref in refs):
        raise AnalyzerError('Read each cited source range before saving this evidence relationship')


def verification_checks(store, run, checks):
    """Return mechanical qualifications without interpreting the test's purpose."""
    from .session_diagnostics import has_primary_result, source_role
    rows = scope_rows(store, run)
    positions = {r['id']:(i, r['agent_id']) for i, r in enumerate(rows)}
    results = []
    for check in checks:
        inspected_refs(store, run, check['references'])
        changed = check['relevant_change_event_ids']
        if len(set(changed)) != len(changed) or set(changed) - positions.keys():
            raise AnalyzerError('Relevant changes must be unique event identities in this scope')
        # These are identity-only ordering anchors, not authored source captions.
        # Scope and full-text exposure still apply.
        for sid in changed: inspected_refs(store, run, [{'source_id':sid}], reader_facing=False)
        sid = check.get('check_event_id')
        if sid and (sid not in positions or sid not in {r['source_id'] for r in check['references']}):
            raise AnalyzerError('A check event must be a cited scoped event')
        if sid and source_role(store, run, sid) not in ('tool_result', 'system_status'):
            raise AnalyzerError('A check event must identify a recorded result, not a call or completion claim')
        predates = [c for c in changed if sid and positions[c][1] == positions[sid][1] and positions[c][0] > positions[sid][0]]
        incomparable = [c for c in changed if not sid or positions[c][1] != positions[sid][1]]
        issues = []
        if predates: issues.append('check_predates_relevant_change')
        if incomparable: issues.append('change_order_not_comparable_in_this_agent_trajectory')
        if check['scope_relation'] in ('narrower', 'unknown'): issues.append('verification_scope_' + check['scope_relation'])
        if check['revision_relation'] in ('earlier', 'unknown'): issues.append('verification_revision_' + check['revision_relation'])
        if check['outcome'] != 'passed': issues.append('verification_' + check['outcome'])
        if not has_primary_result(store, run, check['references']): issues.append('no_primary_verification_result')
        results.append({'adequate_for_completion':not issues, 'qualifications':issues,
                        'predates_change_event_ids':predates, 'order_unknown_change_event_ids':incomparable,
                        'basis':'Recorded ordering and reference prerequisites; scope, revision applicability and pass interpretation are Claude judgments.'})
    return results


def current_map(store, investigation_id):
    from .session_investigation import records
    from .session_review import active_versions
    values = active_versions(records(store, investigation_id, 'requirement_map'), 'requirement_map')
    return values[0] if values else None


def map_coverage(store, run, requirement_map):
    from .session_investigation import accounting
    main = {r['id'] for r in scope_rows(store, run) if r['agent_id']=='main'}
    requests = {t['request_event_id'] for t in accounting(store, run)['turns'] if t['request_event_id'] in main}
    mapped = {r['source_id'] for item in requirement_map['requirements'] for r in item['intent_references']}
    mapped |= {r['source_id'] for item in requirement_map['requirements'] for change in item['intent_changes'] for r in change['references']}
    context = {r['source_id'] for item in requirement_map['context_only'] for r in item['references']}
    return {'main_request_count':len(requests), 'population':'captured_main_task_requests',
            'coverage_status':'empty_population' if not requests else 'partial' if requests-mapped-context else 'all_observed_requests_referenced',
            'mapped_request_ids':sorted(requests & mapped),
            'context_only_request_ids':sorted(requests & context), 'unmapped_request_ids':sorted(requests - mapped - context),
            'limitation':'A referenced request may contain more requirements than were identified. Mapping and reading are not fulfillment or proof of inventory completeness.'}


def save_requirement_map(store, investigation_id, requirement_map):
    from .session_contract import REQUIREMENT_MAP
    from .session_investigation import active_run, put_record, validate_payload, records
    from .session_diagnostics import has_primary_result
    run = active_run(store, investigation_id)
    validate_payload(requirement_map, REQUIREMENT_MAP)
    previous = current_map(store, investigation_id)
    if previous and requirement_map.get('revision_of') != previous['id']:
        # Exact resubmission is idempotent, but a second divergent map must revise.
        if previous['requirement_map'] == requirement_map: return previous
        raise AnalyzerError('Revise the current requirement map; do not create competing inventories')
    if not previous and requirement_map.get('revision_of'):
        raise AnalyzerError('No current requirement map to revise')
    items = requirement_map['requirements']
    keys = [item['key'] for item in items]
    if len(set(keys)) != len(keys): raise AnalyzerError('Requirement keys must be unique')
    fingerprints = [(i['description'].strip().casefold(), i['scope'].strip().casefold()) for i in items]
    if len(set(fingerprints)) != len(fingerprints): raise AnalyzerError('Merge identical requirements in the same scope')
    old_keys = {i['key'] for v in records(store, investigation_id, 'requirement_map') for i in v['requirement_map']['requirements']}
    consumed = set(); prerequisites = {}
    for item in items:
        for refs in (item['intent_references'], item['result_references'], item['artifact_revision']['references']):
            inspected_refs(store, run, refs)
        for change in item['intent_changes']: inspected_refs(store, run, change['references'])
        interpretation = item.get('intent_interpretation')
        if interpretation:
            inspected_refs(store, run, interpretation['references'])
            if interpretation['status']=='ambiguous':
                if len(interpretation['alternatives'])<2:
                    raise AnalyzerError('Ambiguous intent needs at least two plausible readings of the cited instruction')
                if interpretation['outcome_depends_on_interpretation'] and item['status'] not in ('unverified','superseded','withdrawn'):
                    raise AnalyzerError('When plausible intent readings change the outcome, preserve unverified status instead of a confident completion or process-failure claim')
        action = item.get('next_action')
        if action:
            inspected_refs(store, run, action['references'])
            if item['status'] not in ('contradicted','unverified'):
                raise AnalyzerError('A remaining-work action must belong to a not-met or unverified requirement, not completed or inactive intent')
        merged = set(item['merged_from'])
        if merged - old_keys or merged & set(keys) or merged & consumed:
            raise AnalyzerError('Merged keys must name distinct historical requirements removed from this map')
        consumed |= merged
        if set(item['superseded_by']) - set(keys) or item['key'] in item['superseded_by']:
            raise AnalyzerError('Supersession must point to another requirement in the current map')
        if item['status'] == 'superseded' and not item['superseded_by']:
            raise AnalyzerError('A superseded requirement must identify its replacement')
        if item['status'] in ('withdrawn', 'superseded') and not item['intent_changes']:
            raise AnalyzerError('Withdrawal or supersession needs evidence of the change in intent')
        if item['artifact_revision']['state'] == 'known' and (not item['artifact_revision'].get('value') or not item['artifact_revision']['references']):
            raise AnalyzerError('Known artifact revisions need a value and inspected references')
        checks = verification_checks(store, run, item['verification'])
        prerequisites[item['key']] = checks
        delivered_response = delivered_response_check(store, run, item)
        if item['status'] == 'supported_completed':
            if not has_primary_result(store, run, item['result_references']) and not delivered_response:
                raise AnalyzerError('Supported completion needs primary result or artifact evidence. For requested response content, declare delivered_response_evidence; a claim about execution is insufficient')
            if item['verification_required'] and not any(c['adequate_for_completion'] for c in checks):
                raise AnalyzerError('Supported completion needs a passed same-goal check of the relevant revision; narrowed, stale or missing checks leave it unverified')
        if item['status'] == 'unverified' and not item['missing_evidence']:
            raise AnalyzerError('An unverified requirement must say what evidence is missing')
    if previous:
        prior = {i['key'] for i in previous['requirement_map']['requirements']}
        if prior - set(keys) - consumed:
            raise AnalyzerError('Preserve prior requirements as withdrawn/superseded or explicitly merge them; do not silently drop intent')
        old={i['key']:i for i in previous['requirement_map']['requirements']}
        for item in items:
            inherited=[old[k] for k in [item['key']]+item['merged_from'] if k in old]
            historical_sources={r['source_id'] for i in inherited for r in i['intent_references']}
            kept={r['source_id'] for r in item['intent_references']} | {r['source_id'] for c in item['intent_changes'] for r in c['references']}
            if historical_sources-kept:raise AnalyzerError('Preserve the original intent sources when revising or merging requirements')
    by_key={i['key']:i for i in items}
    visited={}
    def cycle(key):
        if visited.get(key)==1:return True
        if visited.get(key)==2:return False
        visited[key]=1
        if any(cycle(next_key) for next_key in by_key[key]['superseded_by']):return True
        visited[key]=2;return False
    if any(cycle(key) for key in by_key):raise AnalyzerError('Requirement supersession cannot contain a cycle')
    for group in requirement_map['context_only']: inspected_refs(store, run, group['references'])
    if requirement_map['inventory_status']=='partial' and not requirement_map['limitations']:
        raise AnalyzerError('A partial requirement inventory must retain its limits')
    body = {'requirement_map':requirement_map, 'verification_prerequisites':prerequisites,
            'request_coverage':map_coverage(store, run, requirement_map), 'policy_version':VERSION,
            'interpretation_basis':'Claude-authored requirements, status, scope and revision relationships; mechanical checks do not establish entailment.'}
    rid = put_record(store, run, 'requirement_map', body)
    return {'id':rid, **body}
