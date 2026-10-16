"""Read-only conversational discovery and inspection of captured accounting.

No model calls, transcript disclosure, or edits to saved Claude judgments.
"""
from .engine import get_evidence
from .session_scope import entities, get_run, get_scope, log_access
from .util import AnalyzerError, bounded, integer, strict_json


def list_session_investigations(store, analysis_id, session_id=None, limit=20, offset=0):
    bounded(limit, 1, 200, 'limit'); bounded(offset, 0, 10000000, 'offset')
    store.analysis(analysis_id)
    items = []
    with store.connect() as db:
        for row in db.execute('SELECT payload FROM session_runs WHERE analysis_id=? ORDER BY created_at DESC,id DESC', (analysis_id,)):
            run = strict_json(row['payload'])
            if session_id is not None and run['root_session_id'] != session_id:
                continue
            # No titles, purpose, conclusions or excerpts in metadata discovery.
            items.append({k: run.get(k) for k in ('id', 'analysis_id', 'scope_id', 'root_session_id',
                         'created_at', 'run_status', 'conclusion', 'revision_of')})
    return {'analysis_id': analysis_id, 'items': items[offset:offset + limit], 'total': len(items),
            'next_offset': offset + limit if offset + limit < len(items) else None,
            'ordering': 'Most recently created saved investigation first; not report file modification time.',
            'execution_state': 'not_observed', 'freshness': 'not_compared_to_live_source',
            'limits': 'A saved running state does not establish a live process. Completed investigation does not mean the developer task succeeded. Listing does not bind this host; opening one does.'}


def _numeric_field(record, path):
    """Expose only the numeric telemetry whitelist, never arbitrary source text."""
    value = record
    for key in path.split('.'):
        if not isinstance(value, dict):
            return {'state': 'unavailable_parent', 'value': None}
        if key not in value:
            return {'state': 'absent', 'value': None}
        value = value[key]
    if value is None:
        return {'state': 'null', 'value': None}
    if integer(value):
        return {'state': 'recorded', 'value': value}
    return {'state': 'invalid', 'value': None, 'value_type': type(value).__name__}


USAGE_FIELDS = ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens',
                'output_tokens_details.thinking_tokens', 'cache_creation.ephemeral_5m_input_tokens',
                'cache_creation.ephemeral_1h_input_tokens')


def inspect_response_accounting(store, investigation_id, response_id, limit=20, offset=0):
    bounded(limit, 1, 200, 'limit'); bounded(offset, 0, 10000000, 'offset')
    run = get_run(store, investigation_id)
    scope = get_scope(store, run)
    response = next((r for r in entities(store, run, 'response') if r['id'] == response_id), None)
    if response is None:
        raise AnalyzerError('Response identity is outside this investigation scope')
    # Keep pages small even when a response contains many streaming frames.
    selected = response['evidence'][offset:offset + limit]
    frames = []
    with store.connect() as db:
        for eid in selected:
            row = db.execute('SELECT raw FROM events WHERE dataset_id=? AND id=?', (scope['dataset_id'], eid)).fetchone()
            if row is None:
                frames.append({'source_id': eid, 'state': 'retained_source_unavailable'})
                continue
            raw = strict_json(row['raw'])
            message = raw.get('message')
            usage = message.get('usage') if isinstance(message, dict) else None
            frames.append({'source_id': eid, 'state': 'retained_source',
                'source': get_evidence(store, scope['dataset_id'], eid),
                'api_block_index': _numeric_field(raw, 'apiBlockIndex'),
                'aborted_mid_stream': raw.get('isAbortedMidStream') is True,
                'usage_container': 'object' if isinstance(usage, dict) else ('absent' if isinstance(message, dict) and 'usage' not in message else 'null' if usage is None else 'invalid'),
                'captured_usage_fields': {p: _numeric_field(raw, 'message.usage.' + p) for p in USAGE_FIELDS}})
    request_id = log_access(store, run, 'inspect_response_accounting', {'response_id': response_id, 'limit': limit, 'offset': offset},
                            [{'source_id': eid, 'access_type': 'metadata'} for eid in selected])
    return {'request_id': request_id, 'scope_id': run['scope_id'], 'response_id': response_id,
            'adapter_version': scope['adapter_version'],
            'reconciled': {k: response.get(k) for k in ('tokens', 'usage_status', 'warnings', 'eligible', 'synthetic_basis', 'agent_ids', 'models', 'versions')},
            'frames': frames, 'total': len(response['evidence']),
            'next_offset': offset + limit if offset + limit < len(response['evidence']) else None,
            'disclosure': 'Numeric telemetry whitelist only. Message text, thinking text, signatures, paths and arbitrary usage fields are not returned.',
            'limits': 'Captured fields are observations, not independent provider verification. Frames may update the same response: never sum them. Reconciled input includes uncached input, cache creation and cache reads; reported thinking is inside output. Unknown or invalid fields remain unavailable. Inspect warnings and all relevant frames before accepting a disputed number.'}
