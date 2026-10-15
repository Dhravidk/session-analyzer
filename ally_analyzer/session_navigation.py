"""Local navigation identities and comparison of retained session evidence.

No model calls, title matching, elapsed-time inference, or report-mtime freshness.
Payload hashes use the same canonical encoding as the importer. Comparison is
restricted to the report's main/structurally admitted or explicitly missing agents.
"""
import hashlib
from pathlib import PurePosixPath

from .ingest import LIMITS, companion_entries, identity_from_path
from .util import AnalyzerError, digest, strict_json, timestamp


def session_key(item):
    # Working directories disambiguate conflicting native IDs; literal full paths
    # are never replaced by the abbreviated folder label. Unidentified exports
    # remain path-scoped, rather than merging on their filename.
    identity = [item['folder_path'], item['session_id']] if item.get('explicit_session_id') else [item['relative_path']]
    return digest(identity)[:24]


def report_revision(data):
    scope = data.get('scope', {})
    sources = data.get('sources', {})
    ids = scope.get('event_ids', [])
    records = [sources.get(key, {}) for key in ids]
    complete = bool(ids) and all(r.get('payload_hash') and r.get('agent_id') for r in records)
    gaps = scope.get('capture_gaps', {})
    agents = set(scope.get('agent_ids', ['main']))
    agents.update(x['child_agent_id'] for x in gaps.get('missing_child_traces', []) if x.get('child_agent_id'))
    return {'policy': 'scoped-payloads-v1', 'complete': complete,
            'records': sorted({(r['agent_id'], r['payload_hash']) for r in records if r.get('payload_hash') and r.get('agent_id')}),
            'agents': sorted(agents), 'scope_hash': scope.get('source_snapshot_hash'),
            'auxiliary': data.get('source_capture', {}).get('auxiliary_sha256'),
            'capture_has_diagnostics': bool(gaps.get('source_diagnostics') or gaps.get('unassigned_dataset_diagnostic_count'))}


def read_revision(path, sid):
    """Read the selected native parent/adjacent children with importer limits.

    Cached by file identities/ctime by the caller, never by the report's mtime.
    Invalid/oversized/ambiguous data yields unknown, not a complete comparison.
    """
    children, collection = companion_entries(path)
    if collection['status'] in ('ambiguous_root', 'unsupported_session_identity'):
        raise AnalyzerError(collection['note'])
    entries = [(path.name, path.stat().st_size, lambda: path.open('rb')), *children]
    if sum(size for _, size, _ in entries) > LIMITS['max_expanded_bytes']:
        raise AnalyzerError('Evidence comparison exceeds the import size limit')
    records, warnings, last_activity, auxiliary = set(), [], None, {}
    for name, size, opener in entries:
        if name.endswith('.meta.json'):
            if size > LIMITS['max_file_bytes']: raise AnalyzerError('Metadata exceeds the import size limit')
            h = hashlib.sha256()
            with opener() as stream:
                for chunk in iter(lambda: stream.read(1024*1024), b''): h.update(chunk)
            auxiliary[auxiliary_key(name)] = h.hexdigest()
            continue
        if size > LIMITS['max_file_bytes']:
            raise AnalyzerError('Evidence comparison exceeds the per-file import limit')
        _, fallback_agent = identity_from_path(name)
        with opener() as stream:
            while True:
                line = stream.readline(LIMITS['max_line_bytes'] + 1)
                if not line: break
                if len(line) > LIMITS['max_line_bytes']:
                    warnings.append('An oversized source record was not compared.')
                    while line and not line.endswith(b'\n'): line = stream.readline(LIMITS['max_line_bytes'] + 1)
                    continue
                if not line.strip(): continue
                try:
                    record = strict_json(line)
                    if not isinstance(record, dict) or not isinstance(record.get('type'), str): raise ValueError()
                    if (record.get('sessionId') or sid) != sid: continue
                    agent = record.get('agentId') or fallback_agent
                    if not isinstance(agent, str): raise ValueError()
                    records.add((agent, digest(record)))
                    at = timestamp(record.get('timestamp'))
                    if at is not None: last_activity = max(last_activity or at, at)
                except (ValueError, UnicodeError, RecursionError):
                    warnings.append('An invalid source record was not compared.')
    return {'records': records, 'warnings': sorted(set(warnings)), 'activity_at': last_activity, 'auxiliary': auxiliary}


def auxiliary_key(name):
    parts = PurePosixPath(name).parts
    index = parts.index('subagents') if 'subagents' in parts else 0
    return '/'.join(parts[max(0,index-1):])


def compare_revision(saved, current):
    unknown = {'state': 'unknown', 'reason': 'The saved evidence cannot be completely compared with the current session.'}
    if not saved or not saved.get('complete'): return unknown
    if current.get('auxiliary') and saved.get('auxiliary') is None:
        return {**unknown, 'reason':'The older report did not retain child-metadata hashes. Reanalyze to compare structural capture inputs.'}
    if saved.get('auxiliary') is not None and saved['auxiliary'] != current.get('auxiliary', {}):
        return {'state':'changed', 'reason':'Child linkage metadata changed. A fresh structural import is needed.'}
    expected = {tuple(x) for x in saved['records']}
    actual = {x for x in current['records'] if x[0] in saved['agents']}
    added, missing = actual - expected, expected - actual
    if added and not missing:
        return {'state': 'new_activity', 'reason': 'Additional records are present in the captured agent trajectories.',
                'added_records': len(added), 'comparison_limits': current['warnings']}
    if missing:
        return {'state': 'changed', 'reason': 'Previously captured records changed or are absent. Additional activity alone does not explain the difference.',
                'added_records': len(added), 'missing_records': len(missing)}
    if current['warnings'] or saved.get('capture_has_diagnostics'):
        return {**unknown, 'reason': ' '.join(current['warnings']) or 'Capture diagnostics prevent a complete evidence comparison.'}
    return {'state': 'current', 'reason': 'Captured source record hashes match the current agent trajectories.'}


def navigation_status(report, freshness, job=None):
    """Freshness, completeness and update state are independent labels."""
    labels = []
    if job and job['status'] in ('queued', 'running'):
        labels.append({'key': 'updating', 'label': 'Updating' if report else 'Analyzing', 'tone': 'amber'})
    elif job and job['status'] in ('failed', 'interrupted'):
        labels.append({'key': 'update_failed', 'label': 'Update failed' if report else 'Analysis failed', 'tone': 'amber'})
    status = report.get('status') if report else None
    analyzed = report and report.get('kind') != 'preview' and status not in ('created', 'not_run')
    if freshness['state'] == 'new_activity' and analyzed:
        labels.append({'key': 'new_activity', 'label': 'New activity', 'tone': 'amber'})
    elif freshness['state'] == 'changed' and analyzed:
        labels.append({'key': 'changed', 'label': 'Source changed', 'tone': 'amber'})
    if not analyzed:
        labels.append({'key': 'not_analyzed', 'label': 'Not analyzed', 'tone': 'gray'})
    elif status in ('partial', 'running'):
        labels.append({'key': 'incomplete', 'label': 'Analysis incomplete', 'tone': 'amber'})
    elif status == 'failed':
        labels.append({'key': 'failed', 'label': 'Analysis failed', 'tone': 'amber'})
    elif status == 'completed':
        if freshness['state'] == 'current' and not labels:
            labels.append({'key': 'ready', 'label': 'Ready', 'tone': 'green'})
    else:
        labels.append({'key': 'unknown', 'label': 'Analysis state unknown', 'tone': 'gray'})
    if analyzed and freshness['state'] == 'unknown':
        labels.append({'key': 'unknown', 'label': 'Freshness unknown', 'tone': 'gray'})
    return labels
