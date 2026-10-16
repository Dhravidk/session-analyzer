#!/usr/bin/env python3
"""Opt-in three-turn Claude plugin test on explicitly synthetic evidence.

Preserves raw host output. Mechanical assertions check tool use, scope and
immutability; an evaluator must separately judge the unedited answers.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ally_analyzer.claude_runner import audit_tool_policy, parse_transcript, run_host
from ally_analyzer.mcp import BY_NAME
from ally_analyzer.store import Store
from scripts.create_diagnostic_fixture import create
from scripts.package_plugin import build_archive

PREFIX = 'mcp__plugin_ally-session-analyzer_ally-session-analyzer__'


def delivered_skills(path):
    """Count verified tool-result delivery, not the model's claim it read a guide."""
    delivered = set()
    for line in path.read_text().splitlines():
        try: row = json.loads(line)
        except ValueError: continue
        message = row.get('message') or {}
        blocks = message.get('content') or []
        for block in blocks if isinstance(blocks, list) else []:
            if block.get('type') != 'tool_result' or block.get('is_error'): continue
            content = block.get('content')
            texts = [content] if isinstance(content, str) else [b.get('text', '') for b in content or [] if isinstance(b, dict)]
            for text in texts:
                try: value = json.loads(text)
                except ValueError: continue
                if not isinstance(value, dict): continue
                for guide in value.get('session_guides', []) + ([value] if 'instructions' in value and 'skill' in value else []):
                    if hashlib.sha256(guide['instructions'].encode()).hexdigest() == guide.get('sha256'):
                        delivered.add(guide['skill'])
    return delivered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--claude', default='claude')
    parser.add_argument('--model', default='sonnet')
    parser.add_argument('--max-budget-usd', type=float, default=3)
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    if args.max_budget_usd <= 0 or args.timeout <= 0: parser.error('Budget and timeout must be positive')
    os.umask(0o077)
    parent = ROOT / '.analysis' / 'claude-conversation'; parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    fixture = create(work / 'synthetic-evidence')
    package = build_archive(work / 'tested-plugin.zip')
    session_id = str(uuid.uuid4())
    env = dict(os.environ, ALLY_ANALYZER_HOME=str(work / 'store'), ALLY_ANALYZER_ALLOW_CONTENT='0')
    for key in ('ALLY_ANALYZER_INVESTIGATION_ID', 'ALLY_ANALYZER_SESSION_ONLY'):
        env.pop(key, None)
    prompts = [
        'Use the session analyzer for this explicitly selected synthetic log: ' + fixture['source'] + '\n'
        'For its main agent, what were total input, uncached input, cache writes, cache reads and output, and what was the cache hit rate? '
        'Check the accounting against captured usage records. Does an input drop prove compaction? '
        'This first question permits metadata only. A local query workspace is fine. Keep the answer focused; do not create a full report or change existing saved judgments.',
        'Follow up on the same session. Controlled excerpts from this synthetic fixture are now authorized through the analyzer. '
        'The last three-case pass means the final artifact was verified, right? '
        'Check that against the request, actual commands/results and subsequent changes. '
        'What should the developer do next, and is fault in the export-check skill or agentset established? '
        'Verify the evidence yourself rather than trusting the archived assistant or our previous answer. '
        'Do not create a full report, rewrite saved judgments, or apply recommendations.',
        'For only the second main-agent task turn, what are the computed cache-write tokens, cache-read tokens and cache-read share? '
        'Exclude the other turns and any child usage. Keep the selection and coverage clear. '
        'Also double-check any absolute claims in your previous reply about whether final verification ran. '
        'Do not change the saved investigation or create a report.'
    ]
    stages = []; remaining = args.max_budget_usd; deadline = time.monotonic() + args.timeout
    iid = None; before = None
    for index, prompt in enumerate(prompts):
        if remaining <= .05 or time.monotonic() >= deadline: break
        cap = remaining * .5 if index < 2 else remaining
        stage = work / ('turn-%d' % (index + 1)); stage.mkdir()
        (stage / 'request.txt').write_text(prompt)
        command = [args.claude, '--plugin-dir', package['path'], '--setting-sources', '', '--tools', 'Skill',
                   '--allowedTools', PREFIX + '*', 'Skill(ally-session-analyzer:explain)',
                   'Skill(ally-session-analyzer:write-report)', 'Skill(ally-session-analyzer:analyze)',
                   '--permission-mode', 'dontAsk', '--model', args.model, '--effort', 'low',
                   '--max-budget-usd', str(cap), '--output-format', 'stream-json', '--verbose',
                   *(['--session-id', session_id] if index == 0 else ['--resume', session_id]), '-p', prompt]
        (stage / 'argv.json').write_text(json.dumps(command, indent=2) + '\n')
        # Keep cwd identical across resume, but preserve each turn's files.
        outcome = run_host(command, work, env, min(300, max(1, int(deadline - time.monotonic()))))
        for name in ('transcript.jsonl', 'stderr.log'):
            (work / name).rename(stage / name)
        calls, finals, host, malformed = parse_transcript(stage / 'transcript.jsonl')
        final = finals[-1] if finals else {}
        (stage / 'answer.md').write_text(final.get('result', ''))
        cost = final.get('total_cost_usd')
        # Resumed host telemetry may be cumulative. Subtracting it again is
        # conservative; missing usage reserves the entire stage allocation.
        remaining -= cost if isinstance(cost, (float, int)) and not isinstance(cost, bool) and cost >= 0 else cap
        entry = {'outcome': outcome, 'final': final, 'host': host, 'calls': calls, 'malformed_lines': malformed,
                 'content_disclosure_enabled': index >= 1, 'budget_cap_usd': cap,
                 'delivered_skills': sorted(delivered_skills(stage/'transcript.jsonl')),
                 'tool_policy': audit_tool_policy(calls, stage/'transcript.jsonl', [PREFIX+n for n in BY_NAME],
                     ('ally-session-analyzer:explain', 'ally-session-analyzer:write-report', 'ally-session-analyzer:analyze')),
                 'transcript_sha256': hashlib.sha256((stage / 'transcript.jsonl').read_bytes()).hexdigest()}
        stages.append(entry)
        if outcome['exit_code'] != 0 or final.get('is_error') or not finals: break
        store = Store(work / 'store')
        with store.connect() as db:
            runs = list(db.execute('SELECT id,payload FROM session_runs ORDER BY created_at,id'))
            saved = [tuple(r) for r in db.execute('SELECT * FROM investigation_records ORDER BY id')]
        if index == 0:
            if len(runs) != 1: break
            iid = runs[0]['id']; before = (runs[0]['payload'], saved)
            env.update(ALLY_ANALYZER_INVESTIGATION_ID=iid, ALLY_ANALYZER_SESSION_ONLY='1', ALLY_ANALYZER_ALLOW_CONTENT='1')
        else:
            entry['saved_judgments_unchanged'] = before == (next(r['payload'] for r in runs if r['id'] == iid), saved)
    calls = [c for s in stages for c in s['calls']]
    names = {c['name'].removeprefix(PREFIX) for c in calls}
    guide_loaded = any('ally-session-analyzer:explain' in s['delivered_skills'] for s in stages) or any(
        c['name'] == 'Skill' and c['input'].get('skill') == 'ally-session-analyzer:explain' for c in calls)
    checks = {'three_successful_turns': len(stages) == 3 and all(s['outcome']['exit_code'] == 0 and not s['final'].get('is_error') for s in stages),
              'conversation_guide_loaded': guide_loaded, 'registered_query_used': 'query_measurement' in names,
              'captured_accounting_inspected': 'inspect_response_accounting' in names,
              'primary_evidence_read': bool(names & {'read_investigation_evidence', 'read_investigation_batch', 'read_turn_evidence'}),
              'saved_judgments_unchanged': len(stages) == 3 and all(s.get('saved_judgments_unchanged') for s in stages[1:]),
              'child_collection_preserved': any(c['name'] == PREFIX + 'import_bundle' for c in calls) and all(c['input'].get('include_subagents', True) for c in calls if c['name'] == PREFIX + 'import_bundle'),
              'writing_guide_delivered': any('ally-session-analyzer:write-report' in s['delivered_skills'] for s in stages) or any(c['name'] == 'Skill' and c['input'].get('skill') == 'ally-session-analyzer:write-report' for c in calls),
              'executed_tools_within_policy': all(s['tool_policy']['executed_calls_within_policy'] for s in stages)}
    evidence = {'mechanical_checks': checks, 'synthetic': True, 'semantic_evaluation': 'requires reading unedited answers and citations',
                'session_id': session_id, 'investigation_id': iid, 'package': package, 'stages': stages,
                'remaining_budget_usd': remaining, 'private_sources_sent': False}
    (work / 'result.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps({'work_dir': str(work), 'mechanical_checks': checks, 'semantic_evaluation': evidence['semantic_evaluation']}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__': raise SystemExit(main())
