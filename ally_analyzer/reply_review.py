"""Shared reply-review evidence checks and cross-process admission rules.

Validation performs ordinary reads/cache/log writes before admission. Only the
short final check-and-append uses BEGIN IMMEDIATE. Never call validators while
holding that writer reservation: they open their own SQLite connections.
"""
from .session_investigation import put_record, records
from .session_review import request_coverage
from .session_scope import projection, scope_rows, summarize_exposure
from .util import AnalyzerError, digest, strict_json

REVIEWER = 'ally-session-analyzer:source-review'
LIMIT = ('Authored source review, not a correctness certificate. MCP validates saved '
         'draft linkage, fresh exposure, literal quotes and reply format; it does not '
         'independently attest caller identity or entailment. Native Agent provenance '
         'must be checked in the host trace. No historical prose was changed.')
REVIEW_KINDS = ('reply_review', 'collection_reply_review')


def review_history(store, owner_id, kind, draft_id, *, connection=None):
    if kind not in REVIEW_KINDS:
        raise AnalyzerError('Unknown reply-review record kind')
    return [r for r in records(store, owner_id, kind, connection=connection) if r['draft_id'] == draft_id]


def accepted_review(history):
    """Keep the established first stored acceptance if legacy duplicates exist.

    Historical rows, including a later conflicting acceptance, are not rewritten.
    Only this canonical acceptance may be returned or retried as a ready answer.
    """
    return next((r for r in history if r['status'] == 'accepted'), None)


def retry_from_history(history, submission, exposure_key):
    accepted = accepted_review(history)
    if accepted and accepted['submission'] == submission:
        return accepted
    repeated = next((r for r in history if r['status'] != 'accepted'
                     and r['submission'] == submission and r.get('exposure_key') == exposure_key), None)
    if repeated:
        return repeated
    if accepted:
        raise AnalyzerError('This draft already has an immutable accepted review; submit a new draft for a new answer')
    if len(history) >= 2:
        raise AnalyzerError('Two review submissions already exist for this draft. Review remains incomplete; do not loop or silently fall back to its initial answer')
    return None


def review_retry(store, owner_id, kind, draft_id, submission, exposure_key):
    """Optional fast path, never authority to append a new submission."""
    return retry_from_history(review_history(store, owner_id, kind, draft_id), submission, exposure_key)


def save_review(store, owner_id, kind, candidate):
    """Atomically admit/reuse a validated candidate across SQLite processes.

    Append-only history is authoritative, including old attempts. No slots or
    accepted flags are reserved separately; failures roll back the whole append.
    Identical retries cannot consume another slot, and conflicting acceptance or
    a third submission cannot pass a stale prevalidation check.
    """
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        history = review_history(store, owner_id, kind, candidate['draft_id'], connection=db)
        repeated = retry_from_history(history, candidate['submission'], candidate['exposure_key'])
        if repeated:
            return repeated
        rid = put_record(store, {'id': owner_id}, kind, candidate, connection=db)
        return {'id': rid, **candidate}


def review_source_state(store, run, after_access_id):
    """One immutable access snapshot for coverage, retry key and quote checks."""
    with store.connect() as db:
        accesses = [strict_json(r[0]) for r in db.execute(
            'SELECT payload FROM investigation_access WHERE investigation_id=? AND id>? ORDER BY id',
            (run['id'], after_access_id))]
    sources = summarize_exposure(accesses)['sources']
    coverage = request_coverage(store, run, sources)
    coverage = {**coverage, 'unread_request_count': len(coverage['unread_requests']),
                'unread_requests': coverage['unread_requests'][:8]}
    return {'sources': sources, 'exposure_key': digest(sources), 'coverage': coverage,
            'fresh_accesses': {a['request_id']: a for a in accesses if a['status'] == 'returned'}}


def fresh_request_coverage(store, run, after_access_id):
    return review_source_state(store, run, after_access_id)['coverage']


def literal_quote_error(store, run, check, fresh_accesses, allow_content):
    """Validate a literal quote in a delivered fresh range, never its meaning."""
    if not allow_content:
        return 'Source text checks are unavailable with content disclosure off; submit no source quotes'
    text, sha, _, _ = projection(store, run, check['source_id'], include_metadata=False)
    access = fresh_accesses.get(check['access_id'])
    if not access:
        return 'The cited read request must belong to this investigation and follow draft creation'
    quote = check['quote']
    if not quote.strip():
        return 'A nonblank literal quote is required'
    for delivery in access['deliveries']:
        if (delivery['source_id'] == check['source_id'] and delivery.get('text_sha256') == sha
                and delivery.get('access_type') == 'read'
                and quote in text[delivery['start_char']:delivery['end_char']]):
            return None
    return 'The quote must match a freshly read, fingerprinted source range (a search snippet or metadata is insufficient)'


def review_source_issues(store, run, state, source_checks, allow_content):
    """Shared per-root fresh exposure, literal-source and aspect requirements."""
    issues = []
    if allow_content and state['coverage']['unread_request_count']:
        issues.append({'code': 'review_requests_not_reread',
                       'message': 'Reread remaining requests/updates after this draft was saved. Refresh draft coverage for unread IDs.'})
    for check in source_checks:
        try:
            error = literal_quote_error(store, run, check, state['fresh_accesses'], allow_content)
        except AnalyzerError:
            error = 'The source is unavailable or outside this investigation; no quote was verified'
        if error:
            issues.append({'code': 'invalid_review_source', 'source_id': check['source_id'], 'message': error})
    if allow_content and scope_rows(store, run):
        aspects = {c['aspect'] for c in source_checks}
        for aspect in ('task_outcome', 'instruction_following'):
            if aspect not in aspects:
                issues.append({'code': 'missing_review_' + aspect + '_source',
                               'message': 'Cite fresh original evidence for the ' + aspect + ' assessment, retaining any missing-evidence limit.'})
    return issues
