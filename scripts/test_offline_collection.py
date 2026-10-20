#!/usr/bin/env python3
"""Opt-in accounting check of selected real logs; no Claude or new narrative."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ally_analyzer.engine import analyze_dataset
from ally_analyzer.ingest import import_bundle
from ally_analyzer.session_collection import get_session_collection, start_session_collection
from ally_analyzer.session_scope import get_run
from ally_analyzer.store import Store
from ally_analyzer.util import canonical


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', action='append', required=True, type=Path)
    parser.add_argument('--session-id', action='append', help='Explicit roots when the selected input contains others')
    parser.add_argument('--preserve-output', action='append', default=[], type=Path)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    parent = ROOT/'.analysis/offline-collection'; parent.mkdir(parents=True, exist_ok=True)
    dest = args.output_dir or Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    dest.mkdir(parents=True, exist_ok=True)
    protected = [p.resolve(strict=True) for p in args.source + args.preserve_output]
    before = {str(p): fingerprint(p) for p in protected}
    # An offline arithmetic exercise cannot accidentally spend host/model usage.
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network is forbidden')), \
         patch.object(subprocess, 'Popen', side_effect=AssertionError('Subprocess/model launch is forbidden')):
        store = Store(dest/'store')
        imported = import_bundle(store, args.source)
        aid = analyze_dataset(store, imported['dataset_id'])['analysis_id']
        with store.connect() as db:
            roots = [r[0] for r in db.execute('SELECT DISTINCT session_id FROM events WHERE dataset_id=? AND agent_id=? ORDER BY session_id',
                                             (imported['dataset_id'], 'main'))]
        roots = args.session_id or roots  # Only explicitly selected files were imported.
        selected = start_session_collection(store, aid, roots, 'Offline selected-log accounting check')
        metrics = selected['collection_readout']
        opening = metrics['opening']
        with store.connect() as db:
            accounting_before = [tuple(r) for r in db.execute('SELECT scope_id,kind,id,payload FROM scope_entities ORDER BY scope_id,kind,id')]
            for member in selected['members']:
                run = get_run(store, member['investigation_id'])
                run['analyzer_usage'] = {'cost_usd': '12345', 'input_tokens': 987654321}
                db.execute('UPDATE session_runs SET payload=? WHERE id=?', (canonical(run), run['id']))
        repeated = get_session_collection(store, selected['collection_id'])
        with store.connect() as db:
            accounting_after = [tuple(r) for r in db.execute('SELECT scope_id,kind,id,payload FROM scope_entities ORDER BY scope_id,kind,id')]
            authored_records = db.execute("SELECT COUNT(*) FROM investigation_records WHERE kind != 'session_collection'").fetchone()[0]
        checks = {'source_and_preserved_output_bytes_unchanged': all(fingerprint(p) == before[str(p)] for p in protected),
                  'source_cost_excludes_injected_analyzer_usage': repeated['collection_readout']['opening'] == opening,
                  'canonical_scoped_accounting_unchanged': accounting_before == accounting_after,
                  'every_selected_root_has_separate_scope': len({m['investigation_id'] for m in selected['members']}) == len(roots),
                  'every_recorded_eligible_response_priced': metrics['cost_kind'] == 'priced_usage',
                  'no_authored_findings_or_Claude_output_generated': authored_records == 0}
        result = {'checks': checks, 'collection_id': selected['collection_id'], 'analysis_id': aid,
                  'collection_readout': metrics, 'accounting_coverage': selected['accounting_coverage'],
                  'members': selected['members'], 'protected_sha256': before,
                  'limitations': 'Offline arithmetic/protocol checks, not independent provider accounting validation or a native Claude/style/source-review test.'}
        (dest/'audit.json').write_text(json.dumps(result, indent=2)+'\n')
        text = [opening, *metrics['qualifications'],
                'Offline computed accounting preview only. No Claude narrative or new source review was generated.']
        for member in selected['members']:
            text += [member['session_id'], member['session_readout']['opening']]
        (dest/'cost-preview.md').write_text('\n\n'.join(text)+'\n')
    print(json.dumps({'output_dir':str(dest), 'checks':checks, 'opening':opening}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
