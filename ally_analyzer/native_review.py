"""Host-hook launch reservation and native identity, separate from authored review.

Only trusted Claude hook metadata binds a native agent ID. Short SQLite writer
transactions prevent duplicate fresh launches across processes; no expiry can
silently authorize spending on another reviewer. These records do not certify
source judgments or billable-request completeness.
"""
import re

from .util import AnalyzerError, digest, strict_json, utc_now

REVIEWER = 'ally-session-analyzer:source-review'
TICKET = re.compile(r'\breview_ticket=(review_[a-f0-9]{32})\b')


def launch_state(store, owner_id, draft_kind, draft_id):
    if draft_kind not in ('reply_draft', 'collection_reply_draft'):
        raise AnalyzerError('Unknown native reply draft kind')
    ticket = 'review_' + digest([owner_id, draft_kind, draft_id])[:32]
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT OR IGNORE INTO reply_reviewer_launches '
                   '(ticket,owner_id,draft_kind,draft_id,agent_name,status) VALUES (?,?,?,?,?,?)',
                   (ticket, owner_id, draft_kind, draft_id, 'sa-review-' + ticket[-16:], 'unstarted'))
        row = dict(db.execute('SELECT * FROM reply_reviewer_launches WHERE ticket=?', (ticket,)).fetchone())
    row['instruction'] = (
        'Launch the packaged source-review Agent once, with name=' + row['agent_name'] +
        ', run_in_background=false and review_ticket=' + ticket + ' in its prompt, plus the owner/draft IDs. '
        if row['status'] == 'unstarted' else
        'Resume native agent ' + row['agent_id'] + ' in host session ' + row['host_session_id'] +
        ' using Agent(resume=agent_id) if advertised, otherwise SendMessage(to=agent_id). '
        'Never invoke a fresh Agent. If the host refuses resume, report review incomplete; do not buy a replacement.'
        if row['agent_id'] else
        'A launch was reserved but no native handle is recorded. Review is incomplete; do not launch a replacement or reset the reservation.')
    return row


def _event(db, row, name, session, agent=None):
    db.execute('INSERT INTO reply_reviewer_events(ticket,event,host_session_id,agent_id,created_at) VALUES (?,?,?,?,?)',
               (row['ticket'], name, session, agent, utc_now()))


def _ensure_open(db, row):
    kind = 'reply_review' if row['draft_kind'] == 'reply_draft' else 'collection_reply_review'
    history = [strict_json(r[0]) for r in db.execute(
        'SELECT payload FROM investigation_records WHERE investigation_id=? AND kind=?', (row['owner_id'], kind))]
    history = [r for r in history if r['draft_id'] == row['draft_id']]
    if any(r['status'] == 'accepted' for r in history):
        raise AnalyzerError('This draft already has an accepted answer; retrieve it without another paid review')
    if len(history) >= 2:
        raise AnalyzerError('This draft exhausted its two submissions; retain the incomplete review without another paid launch')


def hook_event(store, payload):
    event = payload.get('hook_event_name')
    session = payload.get('session_id')
    if not isinstance(session, str) or not session:
        raise AnalyzerError('Native reviewer hook needs a host session ID')
    if event == 'PreToolUse':
        tool = payload.get('tool_name')
        args = payload.get('tool_input') or {}
        if tool not in ('Agent', 'SendMessage'):
            return {}
        target = args.get('resume') if tool == 'Agent' else args.get('to')
        match = TICKET.search(args.get('prompt', '')) if tool == 'Agent' else None
        relevant = args.get('subagent_type') == REVIEWER or bool(match)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM reply_reviewer_launches WHERE agent_id=?', (target,)).fetchone() if target else None
            if target and row:
                row = dict(row)
                if match and match[1] != row['ticket']:
                    raise AnalyzerError('The resume target belongs to a different draft')
                if row['host_session_id'] != session:
                    raise AnalyzerError('Resume the original host session before continuing this reviewer')
                _ensure_open(db, row)
                _event(db, row, 'resume_requested', session, target)
                return {}
            if not relevant:
                return {}
            if target:
                raise AnalyzerError('No saved native reviewer matches this resume target')
            if not match:
                raise AnalyzerError('Retrieve the reviewed reply state and include its review_ticket in the Agent prompt')
            row = db.execute('SELECT * FROM reply_reviewer_launches WHERE ticket=?', (match[1],)).fetchone()
            if row is None:
                raise AnalyzerError('Unknown review ticket; retrieve the original draft state')
            row = dict(row)
            _ensure_open(db, row)
            call_id = payload.get('tool_use_id')
            if not isinstance(call_id, str) or not call_id:
                raise AnalyzerError('Native reviewer launch needs the host tool-use ID')
            if row['status'] != 'unstarted':
                if row['status'] == 'launching' and (session, call_id) == (row['host_session_id'], row['tool_use_id']):
                    return {}  # Idempotent hook delivery for the same invocation.
                raise AnalyzerError('This draft already reserved its only fresh reviewer. Resume ' +
                                    (row['agent_id'] or 'the original pending reviewer') + '; do not launch a replacement')
            if db.execute("SELECT 1 FROM reply_reviewer_launches WHERE host_session_id=? AND status='launching'", (session,)).fetchone():
                raise AnalyzerError('Wait for this host\'s pending reviewer to record its native handle')
            db.execute("UPDATE reply_reviewer_launches SET status='launching',host_session_id=?,tool_use_id=? WHERE ticket=?",
                       (session, call_id, row['ticket']))
            _event(db, row, 'fresh_launch_reserved', session)
        return {}
    if event == 'SubagentStart' and payload.get('agent_type') == REVIEWER:
        agent = payload.get('agent_id')
        if not isinstance(agent, str) or not agent:
            raise AnalyzerError('SubagentStart did not supply a native reviewer handle')
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM reply_reviewer_launches WHERE agent_id=? AND host_session_id=?', (agent, session)).fetchone()
            if row:
                _event(db, dict(row), 'resume_started', session, agent)
                return {}
            row = db.execute("SELECT * FROM reply_reviewer_launches WHERE host_session_id=? AND status='launching'", (session,)).fetchone()
            if row is None:
                raise AnalyzerError('No reserved draft for this native reviewer; stop without reading or submitting')
            row = dict(row)
            db.execute("UPDATE reply_reviewer_launches SET agent_id=?,status='started' WHERE ticket=?", (agent, row['ticket']))
            _event(db, row, 'native_handle_saved', session, agent)
        return {'hookSpecificOutput': {'hookEventName': 'SubagentStart', 'additionalContext':
                'Native review identity persisted before source work: review_ticket=' + row['ticket'] +
                '; draft_id=' + row['draft_id'] + '; owner_id=' + row['owner_id'] +
                '. Continue only this saved draft. Do not create another reviewer.'}}
    return {}
