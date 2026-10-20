"""Explicit collection tools; every evidence read still names one member scope."""
from .session_contract import ID, S, arr, enum, obj


def tool_specs(spec):
    assessment = obj({'task_outcome': {**S, 'maxLength':4000}, 'instruction_following': {**S, 'maxLength':4000}})
    body = {'type': 'string', 'minLength': 1, 'maxLength': 30000}
    sessions = arr(obj({'investigation_id': ID, 'compliance': assessment, 'body': body},
                       ['investigation_id', 'compliance']), 1, 20)
    draft = {'collection_id': ID, 'draft_id': ID}
    fields = {'collection_id': ID, 'sessions': sessions, 'body': body}
    checks = arr(obj({'investigation_id': ID, 'aspect': enum('task_outcome', 'instruction_following', 'recommendation'),
                      'source_id': ID, 'access_id': ID, 'quote': {'type': 'string', 'minLength': 1, 'maxLength': 600}, 'basis': S}), maximum=200)
    return [
        spec('start_session_collection', 'Before opening any one investigation, select exactly the intended roots from one analysis. Keeps separate immutable evidence scopes and binds this connection only to those roots. Default combined produces one authored developer handoff; individual produces separate readouts. Repeated identical selection resumes the same collection. This is accounting/selection, not a completed source review.',
             {'analysis_id': ID, 'session_ids': arr(ID, 1, 20), 'purpose': S, 'output_mode': enum('combined', 'individual')},
             ['analysis_id', 'session_ids', 'purpose'], False),
        spec('get_session_collection', 'Open/resume an explicit collection. Return member investigation IDs, each request inventory and cost breakdown, plus deduplicated combined cost/usage. Does not sum overlapping per-session totals or cumulative snapshots. Unselected sessions remain inaccessible.', {'collection_id': ID}, ['collection_id']),
        spec('prepare_collection_reply', 'Required before a general multi-session final answer. Combined mode: submit one complete body and one compliance entry for each root, with exact distinct spans present in that body; omit per-session bodies. Individual mode: omit combined body and supply each session body/compliance. Read all indexed requests/updates in every root first. Valid draft returns review_required; automatically invoke native ally-session-analyzer:source-review with collection/draft IDs. Never self-review or deliver the initial draft. Source costs exclude analyzer/reviewer usage.',
             {**fields, 'requested_details': arr(enum('cache', 'compaction'), maximum=2), 'detail_request': S}, ['collection_id', 'sessions'], False),
        spec('get_collection_reply_draft', 'For the fresh native source-review Agent: immutable batch draft, exact selected member scopes and fresh request coverage per root. Reread each session separately and verify aggregate advice against cited roots and applicable instructions. Optional include_reviews returns retained review attempts/notes for resumption. Source prose remains subject to the operator disclosure policy.', {**draft, 'include_reviews':{'type':'boolean'}}, list(draft)),
        spec('submit_collection_reply_review', 'Packaged native reviewer submits the complete standalone body and distinct visible compliance spans for EVERY selected root. Each fresh literal source check names its member investigation and read request. Reread every indexed request/update after draft creation and cite each root for task outcome and instruction following. Verify cross-session advice without transferring authorization or outcomes. At most two distinct submissions; accepted prose is immutable. No extra per-session reply-review cycle is required.',
             {**fields, 'draft_id': ID, 'notes': S, 'source_checks': checks}, ['collection_id', 'draft_id', 'sessions', 'notes', 'source_checks'], False),
        spec('get_reviewed_collection_reply', 'Return only the accepted immutable source-reviewed handoff, or the required/incomplete review state. Copy ready.reply exactly, including computed combined cost and input/cached input/output/reasoning breakdown. No unreviewed fallback. Backend checks source linkage and format, not semantic truth or caller identity.', draft, list(draft)),
    ]
