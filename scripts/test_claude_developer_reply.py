#!/usr/bin/env python3
"""Opt-in native Claude readout on one explicitly selected real or synthetic log.

This checks the default one-turn native source-review flow, format, tool policy
and preservation, not semantic correctness or a completed full managed report.
Keep every original draft, review, answer and host failure.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ally_analyzer.claude_runner import audit_tool_policy, parse_transcript, run_host
from ally_analyzer.engine import analyze_dataset, canonical_report
from ally_analyzer.ingest import import_bundle
from ally_analyzer.session_investigation import get_session_overview
from ally_analyzer.session_investigation import records
from ally_analyzer.session_scope import start_session_investigation
from ally_analyzer.store import Store
from ally_analyzer.util import canonical
from scripts.package_plugin import build_archive
from scripts.test_claude_readout import READERS, PREFIX, ready_replies


def native_review_activity(path, accepted, answer):
    """Check actual child stream linkage, rather than a model's review assertion."""
    rows = []
    for line in path.read_text().splitlines():
        try: rows.append(json.loads(line))
        except ValueError: continue
    launches, children, results = {}, {}, {}
    for index, row in enumerate(rows):
        blocks = (row.get('message') or {}).get('content', [])
        for block in blocks if isinstance(blocks, list) else []:
            if not isinstance(block, dict): continue
            if block.get('type') == 'tool_use':
                if block.get('name') == 'Agent' and block.get('input', {}).get('subagent_type') == 'ally-session-analyzer:source-review':
                    launches[block['id']] = index
                if row.get('parent_tool_use_id') and row.get('agent_id'):
                    children[block['id']] = {'index':index, 'parent':row['parent_tool_use_id'],
                                              'agent_id':row['agent_id'], 'name':block['name']}
            if block.get('type') == 'tool_result' and not block.get('is_error'):
                texts = block.get('content')
                texts = [texts] if isinstance(texts, str) else [v.get('text', '') for v in texts or [] if isinstance(v, dict)]
                for text in texts:
                    try: result = json.loads(text)
                    except (ValueError, TypeError): continue
                    if isinstance(result, dict): results[block['tool_use_id']] = (index, result)
    read_ids, submitted_ids = set(), set()
    def visit(value):
        if isinstance(value, dict):
            if isinstance(value.get('request_id'), str) and 'text_sha256' in value and 'text' in value:
                read_ids.add(value['request_id'])
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
    for cid, child in children.items():
        if child['parent'] not in launches or cid not in results: continue
        index, result = results[cid]
        if child['name'].endswith(('read_investigation_evidence', 'read_investigation_batch', 'read_turn_evidence')):
            visit(result)
        if child['name'].endswith('submit_session_reply_review') and result.get('status') == 'ready':
            submitted_ids.add(result.get('review_id'))
    reviewed = [r for r in accepted if r['id'] in submitted_ids and r.get('reply') == answer]
    return {'native_launch_count':len(launches), 'native_child_agent_ids':sorted({v['agent_id'] for v in children.values() if v['parent'] in launches}),
            'source_read_request_ids':sorted(read_ids), 'accepted_native_review_ids':sorted(submitted_ids),
            'final_matches_native_review':bool(reviewed),
            'decisive_checks_read_by_native_reviewer':bool(reviewed) and all(
                c['access_id'] in read_ids for r in reviewed for c in r['submission']['source_checks'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--session-id')
    parser.add_argument('--allow-content', action='store_true', help='Authorize controlled excerpts through the selected approved host')
    parser.add_argument('--claude', default='claude')
    parser.add_argument('--model', default='sonnet')
    parser.add_argument('--effort', choices=('low', 'medium', 'high'), default='medium')
    parser.add_argument('--max-budget-usd', type=float, default=3)
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    if not args.allow_content:
        parser.error('This content-dependent check requires explicit --allow-content and an approved Claude host')
    if args.max_budget_usd <= 0 or args.timeout <= 0:
        parser.error('Budget and timeout must be positive')
    os.umask(0o077)
    source = args.source.expanduser().resolve(strict=True)
    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
    parent = ROOT / '.analysis' / 'claude-developer-reply'
    parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    store = Store(work / 'store')
    imported = import_bundle(store, source)
    aid = analyze_dataset(store, imported['dataset_id'])['analysis_id']
    sessions = list(store.items(aid, 'session'))
    if args.session_id:
        sid = args.session_id
    elif len(sessions) == 1:
        sid = sessions[0]['id']
    else:
        parser.error('Select --session-id when the source contains multiple sessions')
    question = 'Analyze this selected session. What happened, were the task and material instructions followed, and what should the developer change, if anything?'
    run = start_session_investigation(store, aid, sid, question)['investigation']
    iid = run['id']
    expected = get_session_overview(store, iid)['session_readout']
    package = build_archive(work / 'tested-plugin.zip')
    before = hashlib.sha256(canonical(canonical_report(store, aid)).encode()).hexdigest()
    env = dict(os.environ, ALLY_ANALYZER_HOME=str(store.root), ALLY_ANALYZER_ALLOW_CONTENT='1',
               ALLY_ANALYZER_SESSION_ONLY='1', ALLY_ANALYZER_INVESTIGATION_ID=iid)
    prompt = ('/ally-session-analyzer:explain ' + iid + '\n' + question + '\n'
              'The operator authorizes controlled excerpts through this approved Claude host. '
              'Answer in this conversation; do not apply changes or create a saved report.')
    (work / 'request.txt').write_text(prompt)
    allowed = [PREFIX + name for name in READERS]
    argv = [args.claude, '--plugin-dir', package['path'], '--setting-sources', '', '--tools', 'Skill,Agent',
            '--allowedTools', *allowed, 'Skill(ally-session-analyzer:explain)', 'Skill(ally-session-analyzer:write-report)', 'Agent(ally-session-analyzer:source-review)',
            '--permission-mode', 'dontAsk', '--model', args.model, '--effort', args.effort,
            '--max-budget-usd', str(args.max_budget_usd), '--no-session-persistence',
            '--output-format', 'stream-json', '--verbose', '-p', prompt]
    (work / 'argv.json').write_text(json.dumps(argv, indent=2) + '\n')
    print(json.dumps({'work_dir': str(work), 'source_session_id': sid, 'budget_usd': args.max_budget_usd}), flush=True)
    outcome = run_host(argv, work, env, args.timeout)
    calls, finals, host, malformed = parse_transcript(work / 'transcript.jsonl')
    final = finals[-1] if finals else {}
    answer = final.get('result', '')
    (work / 'answer.md').write_text(answer)
    plain = re.sub(r'[*_`]', '', answer).strip()
    body = plain[len(expected['opening']):] if plain.startswith(expected['opening']) else plain
    ready = ready_replies(work / 'transcript.jsonl', calls)
    policy = audit_tool_policy(calls, work / 'transcript.jsonl', allowed,
                              ('ally-session-analyzer:explain', 'ally-session-analyzer:write-report'),
                              ('ally-session-analyzer:source-review',))
    reviews = records(store, iid, 'reply_review')
    accepted = [r for r in reviews if r['status'] == 'accepted']
    activity = native_review_activity(work / 'transcript.jsonl', accepted, answer)
    visible = any(all(r['submission']['compliance'][aspect] in answer
                      for aspect in ('task_outcome', 'instruction_following')) for r in accepted)
    coverage = get_session_overview(store, iid)['request_coverage']
    checks = {
        'host_succeeded': outcome['exit_code'] == 0 and bool(final) and not final.get('is_error'),
        'exact_computed_opening_first': answer.startswith(expected['opening']),
        'copied_ready_reply': answer in ready,
        'separate_authored_assessments_visible': visible,
        'one_native_reviewer_invoked': activity['native_launch_count'] == 1,
        'accepted_review_from_native_child': activity['final_matches_native_review'],
        'decisive_sources_reread_by_native_reviewer': activity['decisive_checks_read_by_native_reviewer'],
        'all_captured_task_requests_delivered': coverage['complete_for_observed_population'],
        'default_resource_detail_on_request': not re.search(r'\b(cache|cached|caching|compaction|compact(?:ed|ing)|TTL|cache[- ]write)\b', body, re.I),
        'source_accounting_unchanged': before == hashlib.sha256(canonical(canonical_report(store, aid)).encode()).hexdigest(),
        'original_log_unchanged': fingerprint == hashlib.sha256(source.read_bytes()).hexdigest(),
        'executed_calls_within_policy': policy['executed_calls_within_policy'],
    }
    audit = {'source_path': str(source), 'source_sha256': fingerprint, 'source_session_id': sid,
             'investigation_id': iid, 'expected_readout': expected, 'package': package,
             'question': question, 'operator_prompt_count': 1, 'checks': checks, 'request_coverage': coverage, 'review_ids': [r['id'] for r in reviews], 'outcome': outcome, 'host': host, 'host_result': final,
             'native_review_activity': activity, 'tool_policy': policy, 'calls': calls, 'malformed_stream_lines': malformed,
             'limit': 'One native developer-facing turn with the packaged source-review Agent; not a completed full managed investigation. The checks establish saved review/host activity and preservation, not semantic accuracy.'}
    (work / 'audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps({'work_dir': str(work), 'checks': checks, 'analyzer_host_cost_usd': final.get('total_cost_usd')}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
