#!/usr/bin/env python3
"""Explicitly synthetic navigation fixtures. Never calls Claude.

The normal SessionLibrary serves the same routes and renderer. Only this test
server substitutes a controlled runner result, to exercise failed updates without
corrupting a real report or causing a real provider outage.
"""
import argparse
import json
from pathlib import Path
import sys
import threading
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from ally_analyzer.session_library import SessionLibrary, make_server, write_json
from ally_analyzer.session_report import render_report
from ally_analyzer.util import utc_now
from tests.helpers import write_log
from tests.test_session_workflow import session_rows


class SyntheticLibrary(SessionLibrary):
    def snapshot(self):
        return {**super().snapshot(), 'fixture_label':'Synthetic navigation fixtures · Controlled update simulation; no Claude calls.'}

    def execute(self,job,item,fingerprint,budget,timeout):
        if job['action']=='preview':return super().execute(job,item,fingerprint,budget,timeout)
        with self.lock:job['status']='running';self.save()
        threading.Event().wait(8)
        try:
            if item['session_id']=='navigation-retry-fails':
                raise RuntimeError('Synthetic runner failure: no new valid report was produced.')
            current=self.latest_report(item)
            data=json.loads(Path(current['json_path']).read_text())
            data['investigation'].update(id='synthetic-'+uuid.uuid4().hex,created_at=job['started_at'],finished_at=utc_now())
            dest=self.home/'synthetic-updates'/job['id'];dest.mkdir(parents=True)
            write_json(dest/'report.json',data);(dest/'report.html').write_text(render_report(data))
            record=self.register_report(dest/'report.json',dest/'report.html',item['id'],fingerprint,'investigate')
            with self.lock:job.update(status='saved',report_id=record['id'])
        except Exception as exc:
            with self.lock:job.update(status='failed',error=str(exc))
        finally:
            with self.lock:job['finished_at']=utc_now();self.save()


def build(root):
    logs=root/'sessions';logs.mkdir(parents=True)
    cases=[('ready','/synthetic/north/tools/cache','Synthetic · Verify expiration','completed'),
           ('new','/synthetic/north/tools/cache','Synthetic · Repair expiration','completed'),
           ('partial','/synthetic/north/tools/cache','Synthetic · Add timeout handling','partial'),
           ('not-analyzed','/synthetic/north/tools/cache','Synthetic · Inspect boundary cases',None),
           ('retry-fails','/synthetic/south/tools/cache','Synthetic · Verify expiration','completed'),
           ('unknown','/synthetic/services/api','Synthetic · Review saved response','completed'),
           ('long','/synthetic/with/a/very/long/path/that/remains/available/on/demand/extraordinary-package-name/exceptionally-long-test-directory','Synthetic · Preserve the complete request when a very long session title includes implementation details, nested paths and an explicit verification plan','partial')]
    for index,(key,cwd,title,status) in enumerate(cases):
        rows=session_rows()
        for row in rows:row['sessionId']='navigation-'+key
        rows[0]['cwd']=cwd
        rows[0]['message']['content'][0]['text']='Synthetic navigation validation: '+rows[0]['message']['content'][0]['text']
        rows.append({'type':'custom-title','sessionId':'navigation-'+key,'customTitle':title,'timestamp':f'2026-10-15T{18-index:02}:00:00Z'})
        write_log(logs/key/'session.jsonl',rows)
    lib=SyntheticLibrary(logs,root/'state',sys.executable)
    for key,cwd,title,status in cases:
        if status is None:continue
        item=next(x for x in lib.catalog.values() if x['session_id']=='navigation-'+key)
        job=lib.start({'session':item['id'],'action':'preview'});lib.worker.join()
        record=lib.state['reports'][-1];data=json.loads(Path(record['json_path']).read_text())
        data['investigation'].update(title=title,run_status=status,created_at='2026-10-15T08:00:00Z',finished_at='2026-10-15T08:01:00Z',
            summary='Synthetic navigation fixture. This report exercises interface state only; no Claude investigation was run.',stop_reason='Synthetic incomplete fixture.' if status=='partial' else '')
        dest=root/'fixtures'/key;dest.mkdir(parents=True)
        write_json(dest/'report.json',data);(dest/'report.html').write_text(render_report(data))
        saved=lib.register_report(dest/'report.json',dest/'report.html',item['id'],None,'synthetic')
        if key=='unknown':saved['revision']['complete']=False
        # Multiple internal analyses, one visible session. The latest remains current.
        if key=='ready':
            for day in (12,13,14):
                older=json.loads(json.dumps(data));older['investigation'].update(created_at=f'2026-10-{day}T08:00:00Z',finished_at=f'2026-10-{day}T08:01:00Z')
                old=dest/str(day);old.mkdir();write_json(old/'report.json',older);(old/'report.html').write_text(render_report(older))
                lib.register_report(old/'report.json',old/'report.html',item['id'],None,'synthetic')
        if key in ('new','partial'):
            with (logs/key/'session.jsonl').open('a') as f:f.write(json.dumps({'type':'user','sessionId':item['session_id'],'uuid':'new-'+key,'timestamp':'2026-10-15T20:00:00Z','message':{'role':'user','content':'Synthetic later request: also inspect the boundary.'}})+'\n')
    lib.save();lib.refresh();return lib


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);args=p.parse_args()
    root=Path(args.output).resolve()
    if root.exists():raise SystemExit('Choose a new output directory; fixture histories are not overwritten.')
    root.mkdir(parents=True)
    lib=build(root);server,url=make_server(lib)
    write_json(root/'server.json',{'url':url,'synthetic':True});print(url,flush=True)
    server.serve_forever()

if __name__=='__main__':main()
