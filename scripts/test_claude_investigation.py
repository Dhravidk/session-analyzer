#!/usr/bin/env python3
"""Opt-in host smoke test of the production single-session workflow.

Synthetic fixtures only. Keeps every raw output, including unsuccessful runs.
This is not a held-out human quality benchmark.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.helpers import call, response, result, write_log
from tests.test_session_workflow import human


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--claude', default='claude'); p.add_argument('--plugin', default=str(ROOT))
    p.add_argument('--timeout', type=int, default=300); p.add_argument('--reread', action='store_true')
    p.add_argument('--case', choices=['expected-recovery','false-success'], default='expected-recovery')
    args = p.parse_args()
    parent = ROOT / '.analysis' / 'investigation-smoke'; parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='session-v05-', dir=parent))
    source = ROOT / 'tests' / 'fixtures' / 'single-session' / (args.case + '.jsonl')
    question = 'Investigate the captured task, its instructions, outcome and useful remaining actions.'
    if args.reread:
        source = write_log(work / 'late-recovery.jsonl', [human(0, 'Run the available tests and fix the invocation if needed.'),
            call(1, args={'command':'python3 absent_check.py'}), result(2,'tool-1','Exit code 2\nFile not found', True),
            call(3, args={'command':'python3 -m unittest discover'}),
            result(4,'tool-3','Diagnostics\n' + 'Synthetic progress, not the final outcome.\n' * 450 + '\nFinal check outcome: Ran 3 tests. OK.\n')])
        question += ' The check output is long; inspect its final outcome beyond the preview. This is an explicit retrieval smoke test.'
    cmd = [sys.executable, str(ROOT / 'scripts/run_claude_investigation.py'), '--source', str(source), '--work-dir', str(work / 'run'),
           '--claude', args.claude, '--plugin', args.plugin, '--allow-content', '--include-source-text-in-report', '--timeout', str(args.timeout), '--question', question]
    result_ = subprocess.run(cmd)
    audit = json.loads((work / 'run' / 'audit.json').read_text())
    data = json.loads((work / 'run' / 'claude-investigation.json').read_text())
    outcomes = {'completed':audit['host_completed_investigation'], 'origin_checks':audit['origin_and_transport_checks_passed'],
                'writing_skill_invoked':audit['writing_skill_invoked']}
    if not args.reread and args.case == 'expected-recovery':
        outcomes['expected_negative_test_not_a_pending_fix'] = data['investigation']['conclusion']=='no_action_supported' and not data['recommendations'] and any(i['incident']['expectedness']=='expected' and i['incident']['resolution']=='recovered' for i in data['incidents'])
    elif not args.reread:
        outcomes['false_success_identified'] = data['investigation']['conclusion']=='findings' and bool(data['incidents'])
        outcomes['uninspected_code_not_ready'] = all(v['status']!='ready_for_review' for v in data['validation'].values())
    else:
        outcomes['late_text_read'] = any(c['name'].endswith('__read_investigation_evidence') and c['input'].get('start_char',0)>10000 for c in audit['calls'])
    summary = {'case':args.case,'reread':args.reread,'checks':outcomes,'directory':str(work),'limitation':'Transport and narrow fixture checks only; inspect semantic output separately.'}
    (work / 'smoke-results.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    return 0 if all(outcomes.values()) and result_.returncode==0 else 1


if __name__=='__main__': raise SystemExit(main())
