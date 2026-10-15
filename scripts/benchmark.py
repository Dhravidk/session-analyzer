#!/usr/bin/env python3
"""Repeatable synthetic scale check; not a representative 2 GiB benchmark."""
import argparse
import json
import platform
import resource
import sys
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from ally_analyzer.engine import analyze_dataset, get_metrics
from ally_analyzer.ingest import import_bundle
from ally_analyzer.store import Store
from tests.helpers import call, result, write_log


def main():
    p=argparse.ArgumentParser();p.add_argument('--sessions',type=int,default=500);p.add_argument('--steps',type=int,default=50)
    p.add_argument('--output');args=p.parse_args()
    if not 1<=args.sessions<=1000 or not 1<=args.steps<=100:raise SystemExit('Use 1–1000 sessions and 1–100 steps')
    with tempfile.TemporaryDirectory(prefix='ally-benchmark-') as temp:
        root=Path(temp);source=root/'source';source.mkdir()
        for n in range(args.sessions):
            sid='synthetic-session-%04d'%n;rows=[]
            for step in range(args.steps):
                tid=sid+'-tool-'+str(step)
                c=call(step*2,'Read',args={'file_path':'fixture-%d.txt'%step},tool_id=tid,session=sid,mid=sid+'-msg-'+str(step),request=sid+'-req-'+str(step))
                r=result(step*2+1,tid,'synthetic output '*16,session=sid)
                c['uuid']=sid+'-call-'+str(step);r['uuid']=sid+'-result-'+str(step);rows.extend((c,r))
            write_log(source/(sid+'.jsonl'),rows)
        expanded=sum(p.stat().st_size for p in source.iterdir());store=Store(root/'store')
        start=time.perf_counter();d=import_bundle(store,source,namespace='synthetic-benchmark');imported=time.perf_counter()
        a=analyze_dataset(store,d['dataset_id']);analyzed=time.perf_counter();m=get_metrics(store,a['analysis_id']);queried=time.perf_counter()
        expected=args.sessions*args.steps
        assert m['metrics']['model_responses']['value']==expected
        assert m['metrics']['tools_requested']['value']==expected
        assert m['metrics']['output_tokens']['value']==expected*40
        assert store.analysis(a['analysis_id'])['summary']['sessions_count']==args.sessions
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report={'kind':'synthetic_scale_check','python':platform.python_version(),'platform':platform.platform(),
                'sessions':args.sessions,'model_responses':expected,'tool_calls':expected,'raw_records':expected*2,
                'expanded_bytes':expanded,'import_seconds':round(imported-start,3),'analysis_seconds':round(analyzed-imported,3),
                'metrics_query_seconds':round(queried-analyzed,3),'peak_rss_bytes':peak if sys.platform=='darwin' else peak*1024,
                'counts_verified':True,'limitation':'Synthetic short records; does not establish performance for 2 GiB or full developer sessions.'}
        if args.output:
            Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))


if __name__=='__main__':main()
