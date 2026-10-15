#!/usr/bin/env python3
"""Mechanical retrieval ablation. Does not measure model quality or total speed."""
import argparse
import json
from pathlib import Path
import resource
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from ally_analyzer.engine import analyze_dataset
from ally_analyzer.ingest import import_bundle
from ally_analyzer.session_scope import (get_related_evidence, get_scope, projection, scope_rows, search_investigation_text, start_session_investigation)
from ally_analyzer.store import Store
from ally_analyzer.trajectory import search_trajectory
from ally_analyzer.util import canonical, strict_json
from tests.helpers import call, result as tool_result, write_log
from tests.test_session_workflow import human

# Declared before measurements. A local correctness/retrieval budget, not a
# promised speedup or an acceptance criterion for semantic investigation quality.
BUDGETS = {'events':1001,'warm_queries':5,'max_warm_search_seconds':1.0,'max_graph_query_seconds':0.25,
           'required_retrieval_recall':1.0,'speedup_required':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    args=p.parse_args();output=Path(args.output)
    if output.exists():p.error('Refusing to overwrite an existing benchmark')
    with tempfile.TemporaryDirectory(prefix='ally-retrieval-ablation-') as temp:
        root=Path(temp);rows=[human(0,'Run the supplied synthetic checks.')]
        for n in range(1,1001,2):
            rows.extend([call(n,args={'command':'check --fixture=%d' % n}),tool_result(n+1,'tool-'+str(n),'fixture output\n'+('filler\n'*12)+('needle --λ=[a.b]' if n in (1,501,999) else 'done'))])
        path=write_log(root/'synthetic.jsonl',rows);store=Store(root/'store')
        start=time.perf_counter();ds=import_bundle(store,path);aid=analyze_dataset(store,ds['dataset_id'])['analysis_id']
        canonical_build=time.perf_counter()-start
        start=time.perf_counter();run=start_session_investigation(store,aid,'session-a','Mechanical retrieval benchmark')['investigation']
        scope_and_graph_build=time.perf_counter()-start
        expected={r['id'] for r in scope_rows(store,run) if strict_json(r['raw']).get('uuid') in ('event-2','event-502','event-1000')}
        # Clear only this throwaway text cache to measure its cold population.
        with store.connect() as db: db.execute('DELETE FROM evidence_text')
        start=time.perf_counter()
        search_investigation_text(store,run['id'],'nonmatching cache population probe',max_scan=5000,allow_content=True)
        cache_build=time.perf_counter()-start
        arms={}
        for name in ('legacy_scan','cached_flat','cached_graph'):
            samples=[];recall=[];returned=[]
            for _ in range(BUDGETS['warm_queries']):
                start=time.perf_counter()
                if name=='legacy_scan':
                    answer=search_trajectory(store,aid,'needle --λ=[a.b]',session_id='session-a',max_scan=5000,allow_content=True)
                    found={m['event_id'] for m in answer['matches']}
                else:
                    answer=search_investigation_text(store,run['id'],'needle --λ=[a.b]',max_scan=5000,allow_content=True)
                    found={m['source_id'] for m in answer['matches']}
                samples.append(time.perf_counter()-start);recall.append(len(found & expected)/len(expected));returned.append(len(canonical(answer).encode()))
            arms[name]={'search_seconds':samples,'median_seconds':statistics.median(samples),'max_seconds':max(samples),
                        'recall':min(recall),'returned_bytes':returned,
                        'note':'Graph arm uses the identical cached literal search, so no graph-specific search gain is expected.' if name=='cached_graph' else None}
        start=time.perf_counter()
        graph=get_related_evidence(store,run['id'],'tool:tool-999',relations=['has_result'],depth=1,limit=100)
        graph_seconds=time.perf_counter()-start
        # Direct indexed flat lookup is a fair alternative for this one-hop task.
        start=time.perf_counter()
        with store.connect() as db:
            payload=db.execute("SELECT payload FROM scope_entities WHERE scope_id=? AND kind='tool' AND id='tool-999'",(run['scope_id'],)).fetchone()[0]
        flat=strict_json(payload);flat_seconds=time.perf_counter()-start
        graph_result_ids={e['target'][6:] for e in graph['edges'] if e['relation']=='has_result'}
        result={'budgets':BUDGETS,'dataset':'public synthetic 1001-event single session','arms':arms,
                'canonical_import_analysis_seconds':canonical_build,'scope_and_graph_build_seconds':scope_and_graph_build,
                'text_cache_build_seconds':cache_build,'one_hop_lookup':{'flat_indexed_seconds':flat_seconds,'graph_seconds':graph_seconds,
                  'graph_results_contained_in_flat_evidence':graph_result_ids <= set(flat['evidence'])},
                'storage_bytes':sum(f.stat().st_size for f in store.root.rglob('*') if f.is_file()),
                'process_peak_rss_native_units':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'rss_unit':'bytes on macOS; kilobytes on Linux','model_calls':0,
                'passed':all(a['recall']==1 and a['max_seconds']<=BUDGETS['max_warm_search_seconds'] for a in arms.values()) and graph_seconds<=BUDGETS['max_graph_query_seconds'],
                'limitations':['Warm local retrieval only; cache population reported separately. OS filesystem caches are not reset.',
                    'Scope/graph setup is shared and measured together; this is not independent end-to-end arm timing.',
                    'One-hop flat lookup already has the evidence; graph traversal is not assumed faster.',
                    'No model investigation ablation, diagnostic-quality score or developer review-time measurement.']}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
