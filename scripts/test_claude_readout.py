#!/usr/bin/env python3
"""Opt-in real Claude reply check on labelled synthetic evidence, never private logs.

Preserves raw answers and tool traces. Passing checks concern this two-turn case,
not general semantic quality or guaranteed model compliance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ally_analyzer.claude_runner import audit_tool_policy, parse_transcript, run_host
from ally_analyzer.engine import analyze_dataset, canonical_report
from ally_analyzer.ingest import import_bundle
from ally_analyzer.session_investigation import get_session_overview
from ally_analyzer.session_scope import start_session_investigation
from ally_analyzer.store import Store
from ally_analyzer.util import canonical
from scripts.package_plugin import build_archive
from tests.helpers import call, response, result, write_log
from tests.test_session_workflow import human

PREFIX = 'mcp__plugin_ally-session-analyzer_ally-session-analyzer__'
READERS = ('get_definitions', 'get_session_guide', 'get_session_overview', 'prepare_session_reply', 'get_investigation_records',
           'get_session_reply_draft', 'submit_session_reply_review', 'get_reviewed_session_reply',
           'read_investigation_evidence', 'read_investigation_batch', 'read_turn_evidence',
           'get_related_evidence', 'search_investigation_text', 'get_recorded_failures',
           'get_context_timeline', 'get_tool_output_index', 'get_subagent_details',
           'inspect_response_accounting', 'query_measurement')


def ready_replies(path, calls):
    invocation_ids = {c['id'] for c in calls if c['name'].endswith(('prepare_session_reply', 'get_reviewed_session_reply'))}
    replies = []
    for line in path.read_text().splitlines():
        try: row = json.loads(line)
        except ValueError: continue
        blocks = (row.get('message') or {}).get('content') or []
        for block in blocks if isinstance(blocks, list) else []:
            if block.get('type') != 'tool_result' or block.get('is_error') or block.get('tool_use_id') not in invocation_ids:
                continue
            content = block.get('content')
            texts = [content] if isinstance(content, str) else [v.get('text', '') for v in content or [] if isinstance(v, dict)]
            for text in texts:
                try: result = json.loads(text)
                except (ValueError, TypeError): continue
                if isinstance(result, dict) and result.get('status') == 'ready' and isinstance(result.get('reply'), str):
                    replies.append(result['reply'])
    return replies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--claude', default='claude')
    parser.add_argument('--model', default='sonnet')
    parser.add_argument('--max-budget-usd', type=float, default=2)
    parser.add_argument('--timeout', type=int, default=360)
    args = parser.parse_args()
    if args.max_budget_usd <= 0 or args.timeout <= 0:
        parser.error('Budget and timeout must be positive')
    os.umask(0o077)
    parent = ROOT / '.analysis' / 'claude-readout'; parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    rows = [human(0, 'Write the rollout draft now; drafting is authorized. Keep developer approval required before scaffolding or implementation.'),
            call(1, name='Read', args={'file_path': '/synthetic/planning-facts.txt'}),
            result(2, 'tool-1', 'Synthetic facts: draft scope, risks and verification before implementation.'),
            call(3, name='Read', args={'file_path': '/synthetic/planning-facts.txt'}),
            result(4, 'tool-3', 'Synthetic facts: draft scope, risks and verification before implementation.'),
            {'type': 'system', 'subtype': 'compact_boundary', 'uuid': 'compact', 'sessionId': 'session-a',
             'timestamp': '2026-09-01T12:00:04.500Z',
             'compactMetadata': {'trigger': 'manual', 'preTokens': 200, 'postTokens': 50, 'durationMs': 100}},
            human(5, 'Yes, finish the draft. Approval is required before implementation.'),
            response(6, content=[{'type': 'text', 'text': 'The plan document is still unwritten. May I proceed with drafting it?'}]),
            {'type': 'cost-state', 'uuid': 'cost', 'sessionId': 'session-a', 'totalCostUSD': 12.34, 'startTime': 1000}]
    source = write_log(work / 'synthetic-session.jsonl', rows)
    store = Store(work / 'store')
    dataset = import_bundle(store, source)
    aid = analyze_dataset(store, dataset['dataset_id'])['analysis_id']
    run = start_session_investigation(store, aid, 'session-a', 'Analyze this synthetic session and recommend any useful changes.')['investigation']
    iid = run['id']
    expected = get_session_overview(store, iid)['session_readout']
    package = build_archive(work / 'tested-plugin.zip')
    before = hashlib.sha256(canonical(canonical_report(store, aid)).encode()).hexdigest()
    env = dict(os.environ, ALLY_ANALYZER_HOME=str(store.root), ALLY_ANALYZER_ALLOW_CONTENT='1',
               ALLY_ANALYZER_SESSION_ONLY='1', ALLY_ANALYZER_INVESTIGATION_ID=iid)
    session_id = str(uuid.uuid4()); deadline = time.monotonic() + args.timeout
    allowed = [PREFIX + name for name in READERS]
    prompts = [
        '/ally-session-analyzer:explain ' + iid + '\nAnalyze this selected synthetic session. What should the developer change and why? '
        'Use the captured evidence. Controlled synthetic excerpts are authorized. Answer in this conversation; do not apply changes or create a saved report.',
        'For the same session, now explain its cached-input usage and recorded compaction events. '
        'Give the measured figures and their limits, using the existing accounting tools. Do not change saved judgments.'
    ]
    stages = []; charged = 0.0
    for index, prompt in enumerate(prompts):
        remaining = args.max_budget_usd - charged
        if remaining <= .01 or time.monotonic() >= deadline:
            break
        stage = work / ('turn-' + str(index + 1)); stage.mkdir()
        (stage / 'request.txt').write_text(prompt)
        cap = remaining / (2 - index)
        argv = [args.claude, '--plugin-dir', package['path'], '--setting-sources', '', '--tools', 'Skill,Agent',
                '--allowedTools', *allowed, 'Skill(ally-session-analyzer:explain)', 'Skill(ally-session-analyzer:write-report)', 'Agent(ally-session-analyzer:source-review)',
                '--permission-mode', 'dontAsk', '--model', args.model, '--effort', 'low', '--max-budget-usd', str(cap),
                '--output-format', 'stream-json', '--verbose', *(['--resume', session_id] if index else ['--session-id', session_id]), '-p', prompt]
        (stage / 'argv.json').write_text(json.dumps(argv, indent=2) + '\n')
        outcome = run_host(argv, work, env, max(1, int(deadline - time.monotonic())))
        for name in ('transcript.jsonl', 'stderr.log'):
            (work / name).rename(stage / name)
        calls, finals, host, malformed = parse_transcript(stage / 'transcript.jsonl')
        final = finals[-1] if finals else {}
        answer = final.get('result', '')
        (stage / 'answer.md').write_text(answer)
        cost = final.get('total_cost_usd')
        # Resumed telemetry can be cumulative; reserve conservatively, never assume a free run.
        charged += cost if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0 else cap
        stages.append({'outcome': outcome, 'final': final, 'host': host, 'malformed': malformed,
                       'policy': audit_tool_policy(calls, stage / 'transcript.jsonl', allowed,
                           ('ally-session-analyzer:explain', 'ally-session-analyzer:write-report'),
                           ('ally-session-analyzer:source-review',)),
                       'calls': [c['name'] for c in calls], 'answer': answer,
                       'copied_ready_reply': any(answer.strip() == reply.strip() for reply in ready_replies(stage / 'transcript.jsonl', calls))})
        if outcome['exit_code'] != 0 or final.get('is_error'):
            break
    first = stages[0]['answer'] if stages else ''
    follow = stages[1]['answer'] if len(stages) > 1 else ''
    plain = re.sub(r'[*_`]', '', first).strip()
    body = plain[len(expected['opening']):] if plain.startswith(expected['opening']) else plain
    checks = {
        'two_host_turns_succeeded': len(stages) == 2 and all(s['outcome']['exit_code'] == 0 and not s['final'].get('is_error') for s in stages),
        'exact_computed_opening_first': plain.startswith(expected['opening']),
        'default_reply_uses_preflight': bool(stages) and any(name.endswith('prepare_session_reply') for name in stages[0]['calls']),
        'default_reply_copies_ready_text': bool(stages) and stages[0]['copied_ready_reply'],
        'default_reply_keeps_cache_compaction_detail_on_request': not re.search(r'\b(cache|cached|caching|compaction|compact(?:ed|ing)|TTL|cache[- ]write)\b', body, re.I),
        'requested_followup_explains_both_topics': bool(re.search(r'cache|cached', follow, re.I) and re.search(r'compaction', follow, re.I)),
        'requested_followup_uses_accounting_tools': len(stages) == 2 and any(name.endswith(('get_context_timeline', 'query_measurement', 'inspect_response_accounting')) for name in stages[1]['calls']),
        'source_accounting_unchanged': before == hashlib.sha256(canonical(canonical_report(store, aid)).encode()).hexdigest(),
        'tool_policy_preserved': bool(stages) and all(s['policy']['executed_calls_within_policy'] for s in stages),
    }
    audit = {'synthetic_only': True, 'investigation_id': iid, 'expected_readout': expected, 'package': package,
             'checks': checks, 'stages': [{k:v for k,v in s.items() if k != 'answer'} for s in stages],
             'rejected_unknown_tool_attempts': sum(len(s['policy']['rejected_unknown_tool_attempts']) for s in stages),
             'limit': 'One two-turn formatting/tool-use exercise, not an independent semantic-quality evaluation.'}
    (work / 'audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps({'work_dir': str(work), 'checks': checks}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
