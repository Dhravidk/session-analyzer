#!/usr/bin/env python3
"""Opt-in pricing check on explicitly selected logs, with no model/network calls.

Only computed cost facts are exported. No Claude answer or finding is authored,
revised, or labelled newly reviewed. Private source/output files stay outside Git.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ally_analyzer.engine import analyze_dataset, canonical_report
from ally_analyzer.ingest import import_bundle
from ally_analyzer.session_investigation import get_session_overview
from ally_analyzer.session_scope import start_session_investigation
from ally_analyzer.store import Store
from ally_analyzer.util import canonical


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, action='append', required=True)
    parser.add_argument('--preserve-output', type=Path, action='append', default=[])
    parser.add_argument('--require-priced', action='store_true', help='Fail this check unless all captured responses and four categories are priced')
    args = parser.parse_args()
    sources = [p.expanduser().resolve(strict=True) for p in args.source]
    preserved = {str(p.expanduser().resolve(strict=True)): sha(p.expanduser().resolve(strict=True)) for p in args.preserve_output}
    os.umask(0o077)
    parent = ROOT / '.analysis' / 'automatic-pricing'; parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='offline-', dir=parent))
    results = []
    with patch('socket.socket.connect', side_effect=AssertionError('No network calls in offline pricing')), \
         patch('subprocess.Popen', side_effect=AssertionError('No model/subprocess in offline pricing')):
        for index, source in enumerate(sources, 1):
            fingerprint = sha(source)
            store = Store(work / str(index) / 'store')
            imported = import_bundle(store, source)
            aid = analyze_dataset(store, imported['dataset_id'])['analysis_id']
            sessions = list(store.items(aid, 'session'))
            if len(sessions) != 1:
                parser.error('Select a one-root session file for each --source')
            sid = sessions[0]['id']
            before = hashlib.sha256(canonical(canonical_report(store, aid)).encode()).hexdigest()
            run = start_session_investigation(store, aid, sid, 'Offline pricing check only; no new Claude judgment')['investigation']
            data = get_session_overview(store, run['id'])
            readout, cost = data['session_readout'], data['source_cost']
            checks = {'automatic_verified_catalog': cost['priced_usage']['price_book_source']['kind'] == 'bundled_verified',
                      'source_only_billing_scope': readout['billing_scope'] == 'analyzed_session_only',
                      'source_file_unchanged': fingerprint == sha(source),
                      'canonical_accounting_unchanged': before == hashlib.sha256(canonical(canonical_report(store, aid)).encode()).hexdigest()}
            if args.require_priced:
                checks.update(captured_responses_fully_priced=cost['priced_usage']['complete_for_captured_responses'],
                              four_category_costs_available=all(v['cost_usd'] is not None for v in readout['usage'].values()))
            preview = work / (str(index) + '-cost-preview.md')
            preview.write_text('\n\n'.join([readout['opening'], *readout['qualifications'],
                'Offline computed pricing preview for ' + source.name + '. No new Claude answer or source review was generated; prior Claude output is unchanged.']) + '\n')
            result = {'source_path': str(source), 'source_sha256': fingerprint, 'session_id': sid,
                      'analysis_id': aid, 'investigation_id': run['id'], 'opening': readout['opening'],
                      'preview': str(preview), 'source_cost': cost, 'checks': checks}
            (work / (str(index) + '-audit.json')).write_text(json.dumps(result, indent=2) + '\n')
            results.append(result)
    checks = {'selected_session_checks_passed': all(all(r['checks'].values()) for r in results),
              'prior_outputs_unchanged': all(sha(Path(p)) == value for p, value in preserved.items()),
              'no_model_or_network_calls': True}
    audit = {'checks': checks, 'preserved_output_hashes': preserved, 'sessions': results,
             'limit': 'Offline pricing/accounting and artifact-preservation checks, not a Claude default-flow or writing-quality test.'}
    (work / 'audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps({'work_dir': str(work), 'checks': checks,
                      'openings': [r['opening'] for r in results]}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
