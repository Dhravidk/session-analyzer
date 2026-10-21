#!/usr/bin/env python3
"""Opt-in live checks of an immutable local plugin, including interrupted review.

Private sources, prompts, raw host traces and exact answers stay in .analysis.
This harness never rebuilds the selected ZIP or rewrites model-authored output.
Launch counts and observed model responses are distinct; neither is an invoice.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ally_analyzer.claude_runner import audit_tool_policy, parse_transcript
from ally_analyzer.engine import analyze_dataset, canonical_report
from ally_analyzer.ingest import import_bundle
from ally_analyzer.session_collection import start_session_collection
from ally_analyzer.session_investigation import get_session_overview, records
from ally_analyzer.session_review import request_coverage
from ally_analyzer.session_scope import get_run, start_session_investigation, summarize_exposure
from ally_analyzer.store import Store
from ally_analyzer.util import canonical
from scripts.test_claude_readout import PREFIX, READERS

REVIEWER = 'ally-session-analyzer:source-review'
COLLECTION_TOOLS = ('get_session_collection', 'prepare_collection_reply', 'get_collection_reply_draft',
                    'submit_collection_reply_review', 'get_reviewed_collection_reply')
SOURCE_READERS = ('read_investigation_evidence', 'read_investigation_batch', 'read_turn_evidence')


def stream_rows(path):
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass  # A killed host can leave one partial line; raw bytes survive.
    return rows


def blocks(row):
    value = (row.get('message') or {}).get('content', [])
    return [b for b in value if isinstance(b, dict)] if isinstance(value, list) else []


def tool_values(block):
    content = block.get('content')
    texts = [content] if isinstance(content, str) else [b.get('text', '') for b in content or [] if isinstance(b, dict)]
    for text in texts:
        try:
            value = json.loads(text)
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict):
            yield value


def read_ids(value):
    found = set()
    if isinstance(value, dict):
        if isinstance(value.get('request_id'), str) and 'text_sha256' in value and 'text' in value:
            found.add(value['request_id'])
        for item in value.values():
            found.update(read_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(read_ids(item))
    return found


def reviewer_activity(rows, known_agent_ids=()):
    """Deduplicate stream frames, and link actual child usage/reads/submissions.

    A resumed Agent tool call is not a new reviewer. A model response with
    reported usage is counted once by message ID, never by its streaming frames.
    Unknown/missing telemetry is retained as a limit, not treated as zero spend.
    """
    launches, candidates, child_calls, agents, messages, submitted, reads = {}, {}, {}, set(), {}, set(), set()
    for row in rows:
        for b in blocks(row):
            if b.get('type') == 'tool_use' and b.get('name') in ('Agent', 'SendMessage'):
                value = b.get('input', {})
                candidates[b['id']] = ({**value, 'resume':value.get('to'), 'resume_tool':'SendMessage'}
                                       if b['name'] == 'SendMessage' else value)
                if b.get('input', {}).get('subagent_type') == REVIEWER:
                    launches[b['id']] = b['input']
    # A host may omit subagent_type when resuming a known native agent.
    known_agents = set(known_agent_ids) | {r['agent_id'] for r in rows if r.get('agent_id') and r.get('parent_tool_use_id') in launches}
    for call_id, value in candidates.items():
        if value.get('resume') in known_agents:
            launches[call_id] = value
    for row in rows:
        if row.get('parent_tool_use_id') not in launches and row.get('agent_id') not in known_agents:
            continue
        aid = row.get('agent_id')
        if aid:
            agents.add(aid)
        message = row.get('message') or {}
        usage = message.get('usage')
        if aid and message.get('role') == 'assistant' and message.get('id') and isinstance(usage, dict):
            key = (aid, message['id'])
            if key not in messages or usage.get('output_tokens', 0) >= messages[key]['usage'].get('output_tokens', 0):
                messages[key] = {'agent_id': aid, 'message_id': message['id'], 'model': message.get('model'), 'usage': usage}
        for b in blocks(row):
            if b.get('type') == 'tool_use':
                child_calls[b['id']] = b.get('name', '')
    # Tool-result rows may omit parent/agent metadata; tool-use IDs supply linkage.
    for row in rows:
        for b in blocks(row):
            if b.get('type') != 'tool_result' or b.get('is_error'):
                continue
            name = child_calls.get(b.get('tool_use_id'), '')
            for value in tool_values(b):
                if name.endswith(SOURCE_READERS):
                    reads.update(read_ids(value))
                if name.endswith(('submit_session_reply_review', 'submit_collection_reply_review')) and value.get('status') == 'ready':
                    submitted.add(value.get('review_id'))
    usage_messages = list(messages.values())
    positive = [m for m in usage_messages if any(isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0
                for k, v in m['usage'].items() if k.endswith('_tokens'))]
    actual = {r.get('parent_tool_use_id') for r in rows if r.get('agent_id') in agents}
    return {'agent_call_count': len(launches),
            'attempted_fresh_reviewer_launches': sum(not v.get('resume') for v in launches.values()),
            'fresh_reviewer_launches': sum(not v.get('resume') and key in actual for key, v in launches.items()),
            'resume_calls': sum(bool(v.get('resume')) for v in launches.values()),
            'resume_targets': sorted({v['resume'] for v in launches.values() if v.get('resume')}),
            'agent_ids': sorted(agents), 'observed_reviewer_model_responses': len(positive),
            'model_responses': usage_messages, 'source_read_request_ids': sorted(reads),
            'accepted_native_review_ids': sorted(submitted),
            'agent_calls': [{'tool_use_id': key, **value} for key, value in launches.items()],
            'limit': 'Observed native launches, identities and model responses with usage; interrupted in-flight requests may lack final usage. Not provider billing.'}


def interruption_point(rows):
    """Interrupt after a native reviewer has actually received a source read."""
    activity = reviewer_activity(rows)
    if activity['source_read_request_ids'] and activity['agent_ids']:
        return {'reviewer_ids': activity['agent_ids'], 'read_request_ids': activity['source_read_request_ids'],
                'observed_reviewer_model_responses': activity['observed_reviewer_model_responses']}
    return None


def native_request_coverage(store, members, draft, request_ids):
    """Credit only fresh reads linked to the actual native child in the trace."""
    result = {}
    for member in members:
        iid = member['investigation_id']
        marker = draft['after_access_ids'][iid] if 'after_access_ids' in draft else draft['after_access_id']
        with store.connect() as db:
            accesses = [json.loads(r[0]) for r in db.execute(
                'SELECT payload FROM investigation_access WHERE investigation_id=? AND id>? ORDER BY id', (iid, marker))]
        delivered = summarize_exposure([a for a in accesses if a['request_id'] in request_ids])['sources']
        result[iid] = request_coverage(store, get_run(store, iid), delivered)
    return result


def stop_process(proc, first_signal):
    for sig, seconds in ((first_signal, 5), (signal.SIGTERM, 2), (signal.SIGKILL, 2)):
        if proc.poll() is not None:
            break
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            break
        try:
            proc.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            continue
    proc.wait(timeout=2)


def run_stage(command, cwd, stage, env, timeout, interrupt=False, snapshot=None):
    """Bounded file-backed capture, with guaranteed process-group cleanup."""
    started = time.monotonic()
    stopped, timed_out, host_error, point = False, False, None, None
    proc = None
    with (stage / 'transcript.jsonl').open('w') as out, (stage / 'stderr.log').open('w') as err:
        try:
            proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                    stdout=out, stderr=err, start_new_session=True)
            while proc.poll() is None:
                if interrupt:
                    point = interruption_point(stream_rows(stage / 'transcript.jsonl'))
                    if point:
                        if snapshot:
                            snapshot()
                        stopped = True
                        stop_process(proc, signal.SIGINT)
                        break
                if time.monotonic() - started >= timeout:
                    timed_out = True
                    stop_process(proc, signal.SIGTERM)
                    break
                time.sleep(.1)
        except OSError as exc:
            host_error = type(exc).__name__ + ': ' + str(exc)
        finally:
            if proc is not None and proc.poll() is None:
                stop_process(proc, signal.SIGTERM)
    return {'exit_code': proc.returncode if proc else None, 'timed_out': timed_out,
            'host_error': host_error, 'interrupted_after_native_read': stopped,
            'interruption_point': point, 'elapsed_seconds': time.monotonic() - started}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin', type=Path, required=True)
    parser.add_argument('--source', type=Path, action='append', required=True)
    parser.add_argument('--mode', choices=('single', 'combined', 'individual', 'interrupted'), required=True)
    parser.add_argument('--allow-content', action='store_true')
    parser.add_argument('--claude', default='claude')
    parser.add_argument('--model', default='sonnet')
    parser.add_argument('--max-budget-usd', type=float, default=5)
    parser.add_argument('--timeout', type=int, default=900)
    args = parser.parse_args()
    if not args.allow_content or args.max_budget_usd <= 0 or args.timeout <= 0:
        parser.error('An approved content-enabled host, positive budget and timeout are required')
    if args.mode in ('single', 'interrupted') and len(args.source) != 1:
        parser.error('Select exactly one source for this mode')
    os.umask(0o077)
    plugin = args.plugin.resolve(strict=True)
    with zipfile.ZipFile(plugin) as archive:
        version = json.loads(archive.read('.claude-plugin/plugin.json'))['version']
        # Do not silently test different runtime code from the archive's.
        for name in archive.namelist():
            if name.startswith('ally_analyzer/') and name.endswith(('.py', '.json')):
                if archive.read(name) != (ROOT / name).read_bytes():
                    parser.error('Runtime source differs from selected archive: ' + name)
    parent = ROOT / '.analysis' / ('claude-release-' + version)
    parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=args.mode + '-', dir=parent))
    saved_plugin = work / 'tested-plugin.zip'
    shutil.copyfile(plugin, saved_plugin)
    package = {'path': str(saved_plugin), 'original': str(plugin), 'version': version,
               'sha256': hashlib.sha256(saved_plugin.read_bytes()).hexdigest()}
    sources = [p.resolve(strict=True) for p in args.source]
    fingerprints = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    store = Store(work / 'store')
    aid = analyze_dataset(store, import_bundle(store, sources)['dataset_id'])['analysis_id']
    roots = [p.stem for p in sources]
    captured = {r['id'] for r in store.items(aid, 'session')}
    if set(roots) - captured:
        parser.error('Source basenames must identify the intended captured roots')
    question = 'Analyze the selected session' + ('s' if len(roots) > 1 else '') + '. What happened, were the tasks and material instructions followed, and what should the developer change, if anything?'
    collection_mode = args.mode in ('combined', 'individual')
    if collection_mode:
        selected = start_session_collection(store, aid, roots, question, args.mode)
        owner, members = selected['collection_id'], selected['members']
        expected = selected['collection_readout']
        draft_kind, review_kind = 'collection_reply_draft', 'collection_reply_review'
    else:
        owner = start_session_investigation(store, aid, roots[0], question)['investigation']['id']
        members = [{'session_id': roots[0], 'investigation_id': owner}]
        expected = get_session_overview(store, owner)['session_readout']
        draft_kind, review_kind = 'reply_draft', 'reply_review'
    before = hashlib.sha256(canonical(canonical_report(store, aid)).encode()).hexdigest()
    env = dict(os.environ, ALLY_ANALYZER_HOME=str(store.root), ALLY_ANALYZER_ALLOW_CONTENT='1', ALLY_ANALYZER_SESSION_ONLY='1')
    for key in ('ALLY_ANALYZER_INVESTIGATION_ID', 'ALLY_ANALYZER_COLLECTION_ID'):
        env.pop(key, None)
    env['ALLY_ANALYZER_COLLECTION_ID' if collection_mode else 'ALLY_ANALYZER_INVESTIGATION_ID'] = owner
    # Install and exercise the actual packaged public command in this run's
    # temporary project. Never change the operator's personal Claude skills.
    installer = work / 'install_analyze.py'
    with zipfile.ZipFile(saved_plugin) as archive:
        installer.write_bytes(archive.read('scripts/install_analyze.py'))
    subprocess.run([sys.executable, '-I', str(installer), '--config-dir', str(work / '.claude')],
                   capture_output=True, text=True, check=True, timeout=10)
    prompt = ('/analyze ' + owner + (' --separate' if args.mode == 'individual' else '') + '\n' + question + '\n'
              'The operator authorizes controlled excerpts through this approved Claude host. Answer in this conversation; do not apply changes or create a saved report.')
    allowed = [PREFIX + name for name in (*READERS, *COLLECTION_TOOLS)]
    session_id = str(uuid.uuid4())
    stages, rows, charged, boundary_snapshot = [], [], 0.0, []
    started = time.monotonic()
    print(json.dumps({'work_dir': str(work), 'mode': args.mode, 'package_sha256': package['sha256'],
                      'max_budget_usd': args.max_budget_usd}), flush=True)
    for index in range(2 if args.mode == 'interrupted' else 1):
        remaining = args.max_budget_usd - charged
        if remaining <= .05 or time.monotonic() - started >= args.timeout:
            break
        stage = work / ('stage-' + str(index + 1))
        stage.mkdir()
        if index:
            prompt = 'Continue the interrupted analysis from its saved progress. Resume the same draft and source-review agent rather than restarting the review.'
        cap = remaining / 2 if args.mode == 'interrupted' and not index else remaining
        with store.connect() as db:
            handles = [r[0] for r in db.execute('SELECT agent_id FROM reply_reviewer_launches WHERE owner_id=? AND host_session_id=? AND agent_id IS NOT NULL', (owner, session_id))]
        command = [args.claude, '--plugin-dir', str(saved_plugin), '--setting-sources', 'project', '--tools', 'Skill,Agent,SendMessage,TaskOutput',
                   '--allowedTools', *allowed, 'Skill(analyze)', 'Skill(ally-session-analyzer:analyze)',
                   'Skill(ally-session-analyzer:explain)', 'Skill(ally-session-analyzer:write-report)', 'Agent(' + REVIEWER + ')',
                   *['SendMessage(' + handle + ')' for handle in handles],
                   '--permission-mode', 'dontAsk', '--model', args.model, '--effort', 'medium',
                   '--max-budget-usd', str(cap), '--output-format', 'stream-json', '--verbose', '--forward-subagent-text',
                   *(['--resume', session_id] if index else ['--session-id', session_id]), '-p', prompt]
        (stage / 'request.txt').write_text(prompt)
        (stage / 'argv.json').write_text(json.dumps(command, indent=2) + '\n')
        def snapshot():
            boundary_snapshot.extend(records(store, owner, draft_kind))
            (work / 'interrupted-drafts.json').write_text(json.dumps(boundary_snapshot, indent=2) + '\n')
        outcome = run_stage(command, work, stage, env, max(1, args.timeout - (time.monotonic() - started)),
                            interrupt=args.mode == 'interrupted' and not index, snapshot=snapshot)
        calls, finals, host, malformed = parse_transcript(stage / 'transcript.jsonl')
        final = finals[-1] if finals else {}
        (stage / 'answer.md').write_text(final.get('result', ''))
        stage_rows = stream_rows(stage / 'transcript.jsonl')
        rows.extend(stage_rows)
        policy = audit_tool_policy(calls, stage / 'transcript.jsonl', allowed,
                                  ('analyze', 'ally-session-analyzer:analyze', 'ally-session-analyzer:explain', 'ally-session-analyzer:write-report'), (REVIEWER,), handles)
        entry = {'outcome': outcome, 'final': final, 'host': host, 'malformed_stream_lines': malformed,
                 'tool_policy': policy, 'activity': reviewer_activity(stage_rows, handles),
                 'transcript_sha256': hashlib.sha256((stage / 'transcript.jsonl').read_bytes()).hexdigest()}
        stages.append(entry)
        (stage / 'audit.json').write_text(json.dumps(entry, indent=2) + '\n')
        cost = final.get('total_cost_usd')
        charged += cost if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0 else cap
        if args.mode == 'interrupted' and not index:
            if not outcome['interrupted_after_native_read']:
                break
        elif outcome['exit_code'] != 0 or final.get('is_error') or not final:
            break
    drafts, reviews = records(store, owner, draft_kind), records(store, owner, review_kind)
    accepted = [r for r in reviews if r['status'] == 'accepted']
    answer = stages[-1]['final'].get('result', '') if stages else ''
    (work / 'answer.md').write_text(answer)
    activity = reviewer_activity(rows)
    matching = [r for r in accepted if r.get('reply') == answer and r['id'] in activity['accepted_native_review_ids']]
    bodies = []
    visible = False
    if matching:
        submission = matching[0]['submission']
        entries = submission['sessions'] if collection_mode else [submission]
        bodies = ([submission['body']] if not collection_mode or args.mode == 'combined' else [s['body'] for s in entries])
        visible = all(all(s['compliance'][key] in answer for key in ('task_outcome', 'instruction_following')) for s in entries)
    coverage = ({m['investigation_id']: get_session_overview(store, m['investigation_id'])['request_coverage'] for m in members})
    native_coverage = native_request_coverage(store, members, drafts[0], activity['source_read_request_ids']) if len(drafts) == 1 else {}
    last = stages[-1] if stages else {}
    checks = {
        'host_completed': bool(last) and last['outcome']['exit_code'] == 0 and bool(last['final']) and not last['final'].get('is_error'),
        'exact_computed_cost_opening': answer.startswith(expected['opening']),
        'verbatim_accepted_native_reply': bool(matching),
        'separate_authored_assessments_visible': visible,
        'all_requests_delivered': all(c['complete_for_observed_population'] for c in coverage.values()),
        'all_requests_reread_by_native_reviewer': bool(native_coverage) and all(c['complete_for_observed_population'] for c in native_coverage.values()),
        'exactly_one_persisted_draft': len(drafts) == 1,
        'exactly_one_accepted_review': len(accepted) == 1,
        'review_submission_limit': 1 <= len(reviews) <= 2,
        'one_fresh_native_reviewer_launch': activity['fresh_reviewer_launches'] == 1,
        'one_native_reviewer_identity': len(activity['agent_ids']) == 1,
        'native_reviewer_has_recorded_model_usage': activity['observed_reviewer_model_responses'] > 0,
        'decisive_sources_read_by_native_reviewer': bool(matching) and all(c['access_id'] in activity['source_read_request_ids'] for r in matching for c in r['submission']['source_checks']),
        'default_resource_detail_on_request': bool(bodies) and not any(re.search(r'\b(cache|cached|caching|compaction|compact(?:ed|ing)|TTL|cache[- ]write)\b', body, re.I) for body in bodies),
        'executed_calls_within_policy': bool(stages) and all(s['tool_policy']['executed_calls_within_policy'] for s in stages),
        'source_accounting_unchanged': before == hashlib.sha256(canonical(canonical_report(store, aid)).encode()).hexdigest(),
        'original_sources_unchanged': all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha for path, sha in fingerprints.items()),
        'original_candidate_unchanged': hashlib.sha256(plugin.read_bytes()).hexdigest() == package['sha256'],
    }
    if args.mode == 'interrupted':
        checks.update({'interrupted_during_native_review': bool(stages) and stages[0]['outcome']['interrupted_after_native_read'],
                       'same_draft_and_markers_after_resume': bool(boundary_snapshot) and drafts == boundary_snapshot,
                       'same_reviewer_resumed': activity['resume_calls'] >= 1 and len(activity['agent_ids']) == 1 and set(activity['resume_targets']) == set(activity['agent_ids']),
                       'resumed_reviewer_has_model_usage': len(stages) == 2 and stages[1]['activity']['observed_reviewer_model_responses'] > 0})
    audit = {'mode': args.mode, 'package': package, 'source_fingerprints': fingerprints, 'session_id': session_id,
             'owner_id': owner, 'members': members, 'expected_readout': expected, 'checks': checks,
             'native_review_activity': activity, 'stages': stages, 'coverage': coverage, 'native_request_coverage': native_coverage,
             'draft_ids': [d['id'] for d in drafts], 'review_ids': [r['id'] for r in reviews],
             'host_reported_stage_costs_usd': [s['final'].get('total_cost_usd') for s in stages],
             'interrupted_draft_snapshot': boundary_snapshot,
             'limit': 'Actual approved-host execution, native child linkage and exact saved output; semantic claims still require human source review. Interrupted in-flight billing can be unavailable.'}
    (work / 'audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps({'work_dir': str(work), 'checks': checks, 'fresh_reviewer_launches': activity['fresh_reviewer_launches'],
                      'resume_calls': activity['resume_calls'], 'reviewer_model_responses': activity['observed_reviewer_model_responses'],
                      'host_reported_stage_costs_usd': audit['host_reported_stage_costs_usd']}, indent=2), flush=True)
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
