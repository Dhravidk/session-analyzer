"""Shared reply-review evidence checks and cross-process admission rules.

Validation performs ordinary reads/cache/log writes before registration or
admission. Only their short check-and-append transactions use BEGIN IMMEDIATE.
Never call validators while holding that writer reservation: they open their
own SQLite connections.
"""
import hashlib
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
DRAFT_KINDS = ('reply_draft', 'collection_reply_draft')


def ready_delivery(reply):
    """Transport metadata only: never normalize or rewrite authored characters."""
    return {'delivery':{'action':'copy_reply_exactly_as_final_message',
        'reply_sha256':hashlib.sha256(reply.encode('utf-8')).hexdigest(),
        'reply_characters':len(reply),
        'instruction':"The reply field is the finished source-reviewed document, not a draft to edit. Deliver it as the entire final message with no preface or suffix. Preserve every character, including curly apostrophes, parentheses, semicolons and newlines. Do not apply your own writing conventions, improve punctuation, summarize or reword any paragraph. These metadata fields are not part of the reply."}}


def review_draft_view(draft, coverages):
    """Expose a new draft only after fresh source context, without editing storage.

    Legacy drafts retain their historical read API. New v2 drafts hide authored
    spans until the original requests/instruction context have been delivered.
    This avoids using a parent's prose as a substitute for the fresh review.
    """
    withheld = (draft.get('contract_version') in ('source-review-v2', 'collection-source-review-v2')
                and draft['allow_content'] and any(c['unread_request_count'] for c in coverages))
    view = dict(draft)
    if withheld:
        for field in ('body', 'compliance'):
            view.pop(field, None)
        if 'sessions' in view:
            view['sessions'] = [{k:v for k,v in s.items() if k not in ('body','compliance')} for s in view['sessions']]
    return {'draft':view, 'draft_content_withheld':bool(withheld),
            'review_readiness':'read_sources_first' if withheld else 'ready_to_compare_draft',
            'next_review_step':('Read every remaining fresh request/context source and its continuations; then reload this draft. Do not compose or submit a review yet.' if withheld else
                'Compare the original draft with the evidence just read, check decisive results/counterevidence and submit one complete reviewed body.'),
            'visible_body_policy':{'omit_unrequested_topics':[t for t in ('cache','compaction') if t not in draft.get('requested_details', [])],
                'instruction':'Keep unrequested topics out of visible prose, citations, caveats and prompts; describe a retained instruction without naming its resource mechanism. Do not downgrade an established instruction miss to an open question elsewhere in the same body. Preserve genuine uncertainty about cause or branch delivery separately.'}}


def register_draft(store, owner_id, kind, draft, investigation_ids):
    """Reuse or append one draft per owner/kind/key with its winning boundary.

    Call only after validation has finished opening its own connections. The
    writer reservation covers lookup, all marker reads and the unchanged append.
    Existing duplicates keep their history: the first in established stored
    ordering remains canonical, without moving markers or transferring reviews.
    """
    ids = tuple(investigation_ids)
    if kind not in DRAFT_KINDS or not ids or len(ids) != len(set(ids)):
        raise AnalyzerError('Supply a reply-draft kind and distinct freshness investigation IDs')
    if kind == 'reply_draft' and ids != (owner_id,):
        raise AnalyzerError('A single-session draft must use its own investigation boundary')
    key = digest(draft)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        existing = next((r for r in records(store, owner_id, kind, connection=db) if r['draft_key'] == key), None)
        if existing:
            return existing
        markers = {iid: db.execute('SELECT COALESCE(MAX(id),0) FROM investigation_access WHERE investigation_id=?',
                                  (iid,)).fetchone()[0] for iid in ids}
        boundary = ({'after_access_id': markers[owner_id]} if kind == 'reply_draft'
                    else {'after_access_ids': markers})
        payload = {**draft, 'draft_key': key, **boundary}
        rid = put_record(store, {'id': owner_id}, kind, payload, connection=db)
        return {'id': rid, **payload}


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
    # Resume the first missing range in this draft's fresh snapshot. Reads made
    # before its winning boundary never enter sources and cannot advance a hint.
    for item in coverage['unread_requests']:
        hint = {'start_char':0, 'max_chars':12000}
        seen = [s for s in sources if s['source_id'] == item['source_id']]
        if len(seen) == 1:
            source = seen[0]
            _, sha, _, _ = projection(store, run, item['source_id'], include_metadata=False)
            if sha == source['text_sha256']:
                cursor, end = 0, source['total_characters']
                for left, right in source['delivered_ranges']:
                    if left > cursor:
                        end = left
                        break
                    cursor = max(cursor, right)
                if cursor < end:
                    hint = {'start_char':cursor, 'max_chars':min(12000, end-cursor), 'expected_text_sha256':sha}
        item['resume_read'] = hint
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
                       'message': 'Reread remaining requests, updates and captured skill/retained-context sources after this draft was saved. Refresh draft coverage for unread IDs; assess applicability and counterevidence without treating these sources as new human requests.'})
    context_ids = {c['source_id'] for c in state['coverage'].get('instruction_context_sources', [])}
    if allow_content and context_ids and not any(c['aspect'] == 'instruction_following' and c['source_id'] in context_ids for c in source_checks):
        issues.append({'code': 'missing_instruction_context_check',
                       'message': 'Include an instruction_following source check quoting a captured skill or retained-context source. Explain its applicability or limits and check counterevidence; indexed human requests alone cannot justify a clean compliance verdict.'})
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
