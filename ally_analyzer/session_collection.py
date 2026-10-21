"""Explicit multi-session selection and immutable, source-reviewed handoffs.

Each root keeps its own evidence boundary. Only numeric facts are combined by
Python; Claude authors the entire narrative, including cross-session advice.
"""
from collections import Counter

from .normalize import parse_events
from .native_review import launch_state
from .pricing import configured_prices
from .session_cost import price_captured_responses, source_session_cost
from .session_investigation import accounting, record_by_id, records
from .session_metrics import token_metrics
from .session_readout import developer_readout, prepare_session_reply
from .reply_review import (LIMIT, REVIEWER, accepted_review, fresh_request_coverage,
                           ready_delivery, register_draft, review_draft_view, review_history, review_retry, review_source_issues, review_source_state, save_review)
from .session_review import request_coverage
from .session_scope import (get_run, get_scope, scope_rows,
                            start_session_investigation)
from .util import AnalyzerError, canonical, digest, strict_json, utc_now


def collection(store, collection_id):
    saved = records(store, collection_id, 'session_collection')
    if len(saved) != 1:
        raise AnalyzerError('Unknown session collection ID')
    return saved[0]


def start_session_collection(store, analysis_id, session_ids, purpose, output_mode='combined'):
    if (not isinstance(session_ids, list) or not 1 <= len(session_ids) <= 20
            or len(set(session_ids)) != len(session_ids)):
        raise AnalyzerError('Select one to twenty distinct root session IDs')
    if output_mode not in ('combined', 'individual') or not isinstance(purpose, str) or not purpose.strip():
        raise AnalyzerError('Supply a purpose and combined or individual output mode')
    analysis = store.analysis(analysis_id)
    with store.connect() as db:
        roots = {r[0] for r in db.execute('SELECT DISTINCT session_id FROM events WHERE dataset_id=? AND agent_id=?',
                                         (analysis['dataset_id'], 'main'))}
    if set(session_ids) - roots:
        raise AnalyzerError('Every selection must be a captured root in the selected analysis')
    spec = {'analysis_id': analysis_id, 'session_ids': session_ids, 'purpose': purpose,
            'output_mode': output_mode, 'version': 'session-collection-v1'}
    cid = 'collection_' + digest(spec)[:24]
    if not records(store, cid, 'session_collection'):
        members = []
        for sid in session_ids:
            run = start_session_investigation(store, analysis_id, sid, purpose)['investigation']
            members.append({'session_id': sid, 'investigation_id': run['id']})
        # A deterministic primary key keeps simultaneous identical selections
        # from registering two competing collection payloads. First save wins.
        with store.connect() as db:
            db.execute('INSERT OR IGNORE INTO investigation_records VALUES (?,?,?,?,?)',
                       (cid, 'session_collection', cid, canonical({**spec, 'collection_id': cid, 'members': members}), utc_now()))
    return get_session_collection(store, cid)


def _facts(store, selected):
    # Reconcile the UNION of captured source frames, rather than adding already
    # inclusive per-session counts or cumulative host cost snapshots.
    runs = [get_run(store, m['investigation_id']) for m in selected['members']]
    rows = {r['id']: r for run in runs for r in scope_rows(store, run)}
    conflicts = {key for key, n in Counter(r['logical_key'] for r in rows.values()).items() if n > 1}
    prepared = [{**r, 'record': strict_json(r['raw']), 'identity_conflict': r['logical_key'] in conflicts}
                for r in rows.values()]
    responses = parse_events(prepared)['responses']
    responses = [r for r in responses if r['eligible']]
    prices, origin = configured_prices(store.analysis(selected['analysis_id'])['configuration'])
    usage = price_captured_responses(responses, prices, origin)
    usage['population'] = 'Union of selected root scopes and linked captured children; copied responses reconciled once.'
    missing = [m['session_id'] for m, run in zip(selected['members'], runs)
               if get_scope(store, run)['capture_gaps']['missing_child_traces']]
    cost = {'priced_usage': usage, 'recorded_snapshot': None, 'unavailable_child_traces': missing}
    readout = developer_readout(cost, token_metrics(responses))
    count = len(runs)
    label = '%d selected session%s' % (count, '' if count == 1 else 's')
    readout['opening'] = readout['opening'].replace('Estimated session cost:', 'Estimated cost across ' + label + ':')
    readout['opening'] = readout['opening'].replace('Session cost is unavailable', 'Cost across ' + label + ' is unavailable')
    readout['opening'] = readout['opening'].replace('full session cost is unknown', 'full selected-session cost is unknown')
    readout['population'] = usage['population']
    readout['qualifications'].append('Selected source responses are counted once across logs; per-session totals can overlap. Cumulative host estimates are not added.')
    return readout, {'unique_responses': len(responses), 'source_frames': len(rows),
                     'conflicting_source_identities': len(conflicts), 'missing_child_session_ids': missing}


def get_session_collection(store, collection_id):
    selected = collection(store, collection_id)
    readout, coverage = _facts(store, selected)
    members = []
    for member in selected['members']:
        run = get_run(store, member['investigation_id'])
        requests = request_coverage(store, run)
        members.append({**member,
            'session_readout': developer_readout(source_session_cost(store, run), accounting(store, run)['session']),
            'request_coverage': {**requests, 'unread_request_count': len(requests['unread_requests']),
                                 'unread_requests': requests['unread_requests'][:8]}})
    return {**selected, 'members': members, 'collection_readout': readout, 'accounting_coverage': coverage,
            'notice': 'Selected sessions are separate evidence scopes. A later log does not prove an earlier stalled branch recovered. No authored findings are inferred or changed by this tool.'}


def _check(store, selected, body, sessions, requested_details, detail_request, allow_content):
    expected = [m['investigation_id'] for m in selected['members']]
    if (len(sessions) != len(expected) or {s['investigation_id'] for s in sessions} != set(expected)):
        raise AnalyzerError('Supply one assessment entry for every selected session, with no duplicates or extra scopes')
    combined = selected['output_mode'] == 'combined'
    if combined and (not isinstance(body, str) or not body.strip()):
        raise AnalyzerError('Combined mode requires the complete authored handoff in body')
    if not combined and body is not None:
        raise AnalyzerError('Individual mode uses session bodies; omit the combined body')
    checks = {}
    for item in sessions:
        if combined and 'body' in item:
            raise AnalyzerError('Combined mode uses one unchanged body; omit per-session body fields')
        text = body if combined else item.get('body')
        checks[item['investigation_id']] = prepare_session_reply(store, item['investigation_id'], text,
            requested_details, detail_request, item['compliance'], allow_content,
            _word_limit=450 + 150 * (len(expected) - 1) if combined else 450)
    issues = [{**issue, 'investigation_id': iid} for iid, checked in checks.items() for issue in checked['issues']]
    readout, _ = _facts(store, selected)
    if combined and body.lstrip().startswith(readout['opening']):
        issues.append({'code': 'opening_repeated', 'message': 'Omit the computed opening from your body'})
    return issues, checks, readout


def prepare_collection_reply(store, collection_id, sessions, body=None, requested_details=None,
                             detail_request=None, allow_content=False):
    selected = collection(store, collection_id)
    issues, checked, readout = _check(store, selected, body, sessions, requested_details, detail_request, allow_content)
    if issues:
        return {'status': 'needs_revision', 'issues': issues,
                'request_coverage': {iid: c['request_coverage'] for iid, c in checked.items()}}
    draft = {'body': body, 'sessions': sessions, 'requested_details': requested_details or [],
             'detail_request': detail_request, 'allow_content': allow_content, 'readout': readout,
             'session_readouts': {iid: c['session_readout'] for iid, c in checked.items()},
             'contract_version': 'collection-source-review-v2'}
    did = register_draft(store, collection_id, 'collection_reply_draft', draft,
                         [m['investigation_id'] for m in selected['members']])['id']
    return get_reviewed_collection_reply(store, collection_id, did, allow_content)


def _draft(store, cid, did, allow_content):
    collection(store, cid)
    draft = record_by_id(store, cid, 'collection_reply_draft', did)
    if draft['allow_content'] and not allow_content:
        raise AnalyzerError('This collection draft requires its original content disclosure policy')
    return draft


def _coverage(store, draft):
    return {iid: fresh_request_coverage(store, get_run(store, iid), marker)
            for iid, marker in draft['after_access_ids'].items()}


def get_collection_reply_draft(store, collection_id, draft_id, allow_content=False, include_reviews=False):
    draft = _draft(store, collection_id, draft_id, allow_content)
    coverage = _coverage(store, draft)
    return {'collection_id': collection_id, 'draft_id': draft_id, **review_draft_view(draft, coverage.values()),
            'review_launch': launch_state(store, collection_id, 'collection_reply_draft', draft_id),
            **({'review_history': [r for r in records(store, collection_id, 'collection_reply_review') if r['draft_id'] == draft_id]} if include_reviews else {}),
            'members': collection(store, collection_id)['members'],
            'review_request_coverage': coverage, 'validation_limit': LIMIT,
            'instructions': 'Use the packaged native source-review Agent. Reread every selected session independently after draft creation; do not transfer authorizations or outcomes between roots. Check aggregate advice against each cited root and applicable target. Submit a complete standalone handoff and per-session exact compliance spans. No extra per-session review pass is needed.'}


def get_reviewed_collection_reply(store, collection_id, draft_id, allow_content=False):
    _draft(store, collection_id, draft_id, allow_content)
    reviews = review_history(store, collection_id, 'collection_reply_review', draft_id)
    accepted = accepted_review(reviews)
    if accepted:
        return _result(accepted)
    stopped = len(reviews) >= 2
    return {'status': 'review_incomplete' if stopped else 'review_required', 'collection_id': collection_id,
            'draft_id': draft_id, 'review_attempts': len(reviews), 'reviewer': REVIEWER,
            **({'review_launch': launch_state(store, collection_id, 'collection_reply_draft', draft_id)} if not stopped else {}),
            'next': ('Stop: review remains incomplete; never present the initial draft as reviewed.' if stopped else
                     'Follow review_launch.instruction: include its review_ticket when launching once, or resume its saved native handle. Automatically use the packaged source-review Agent with collection_id and draft_id. Do not launch a replacement, ask for another pass or self-review.'),
            'validation_limit': LIMIT}


def submit_collection_reply_review(store, collection_id, draft_id, sessions, notes, source_checks,
                                    body=None, allow_content=False):
    selected = collection(store, collection_id)
    draft = _draft(store, collection_id, draft_id, allow_content)
    if draft['allow_content'] != allow_content:
        raise AnalyzerError("Review must use the draft's original disclosure policy")
    submission = {'body': body, 'sessions': sessions, 'notes': notes, 'source_checks': source_checks}
    states = {iid: review_source_state(store, get_run(store, iid), marker)
              for iid, marker in draft['after_access_ids'].items()}
    read_key = digest({iid: state['sources'] for iid, state in states.items()})
    repeated = review_retry(store, collection_id, 'collection_reply_review', draft_id, submission, read_key)
    if repeated:
        return _result(repeated)
    issues, checked, _ = _check(store, selected, body, sessions, draft['requested_details'], draft['detail_request'], allow_content)
    coverage = {iid: state['coverage'] for iid, state in states.items()}
    if any(c['investigation_id'] not in states for c in source_checks):
        raise AnalyzerError('A review source check names an unselected session')
    for iid, state in states.items():
        checks = [c for c in source_checks if c['investigation_id'] == iid]
        issues.extend({**issue, 'investigation_id': iid} for issue in
                      review_source_issues(store, get_run(store, iid), state, checks, allow_content))
    saved = {'collection_id': collection_id, 'draft_id': draft_id, 'status': 'rejected' if issues else 'accepted',
             'submission': submission, 'issues': issues, 'exposure_key': read_key,
             'review_request_coverage': coverage, 'validation_limit': LIMIT}
    if not issues:
        parts = [draft['readout']['opening'], *draft['readout']['qualifications']]
        if selected['output_mode'] == 'combined':
            parts.append(body)
        else:
            by_id = {s['investigation_id']: s for s in sessions}
            for member in selected['members']:
                iid = member['investigation_id']
                own = draft['session_readouts'][iid]
                parts.extend(['Session ' + member['session_id'], own['opening'], *own['qualifications'], by_id[iid]['body']])
        saved['reply'] = '\n\n'.join(parts)
    return _result(save_review(store, collection_id, 'collection_reply_review', saved))


def _result(saved):
    return {'collection_id': saved['collection_id'], 'draft_id': saved['draft_id'], 'review_id': saved['id'],
            'status': 'ready' if saved['status'] == 'accepted' else 'needs_revision', 'issues': saved['issues'],
            'review_request_coverage': saved['review_request_coverage'], 'validation_limit': LIMIT,
            **(ready_delivery(saved['reply']) if saved['status'] == 'accepted' else {}),
            **({'reply': saved['reply']} if saved['status'] == 'accepted' else {})}
