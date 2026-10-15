import copy
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from ally_analyzer.session_library import SessionLibrary, folder_label, make_server
from ally_analyzer.session_navigation import navigation_status
from ally_analyzer.session_report import render_report
from ally_analyzer.session_markdown import render_markdown
from ally_analyzer.util import AnalyzerError
from tests.helpers import write_log
from tests.test_session_workflow import session_rows


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.logs=self.root/'projects';self.logs.mkdir()
        rows=session_rows();rows[0]['cwd']='/Users/synthetic/Development/webcore'
        self.log=write_log(self.logs/'encoded-project'/'session-a.jsonl',rows)
        self.library=SessionLibrary(self.logs,self.root/'library',sys.executable)
        self.item=next(iter(self.library.catalog.values()))

    def complete(self, action='preview', **kwargs):
        result=self.library.start(dict(session=self.item['id'],action=action,**kwargs))
        if 'job_id' in result:
            self.library.worker.join(15);self.assertFalse(self.library.worker.is_alive())
            job=self.library.state['jobs'][-1];self.assertEqual(job['status'],'saved',job)
            return next(r for r in self.library.state['reports'] if r['id']==job['report_id'])
        return next(r for r in self.library.state['reports'] if r['id']==result['report_id'])

    def test_folder_labels_discovery_and_no_model_on_browse_or_preview(self):
        self.assertEqual(folder_label('/a/b/c/'),'b/c')
        self.assertEqual(folder_label('C:\\dev\\webcore'),'dev/webcore')
        self.assertEqual(self.item['folder_label'],'Development/webcore')
        child=write_log(self.log.parent/'session-a'/'subagents'/'agent-child.jsonl',session_rows())
        (self.logs/'linked.jsonl').symlink_to(self.log)
        rows=session_rows();rows[0]['cwd']='/another/Development/webcore'
        write_log(self.logs/'other-project'/'session-a.jsonl',rows)
        with patch('ally_analyzer.session_library.subprocess.Popen',side_effect=AssertionError('Browsing must not launch a host')):
            self.library.refresh()
            self.assertEqual(len(self.library.catalog),2)
            self.assertEqual({i['folder_label'] for i in self.library.catalog.values()},{'Development/webcore'})
            report=self.complete()
        self.assertEqual(report['status'],'not_run')
        data=json.loads(Path(report['json_path']).read_text())
        self.assertTrue(data['source_text_included'])
        self.assertFalse(data['recommendations'])
        self.assertIn('Investigation not run',Path(report['html_path']).read_text())
        child.write_text(child.read_text()+'\n')
        self.assertNotEqual(self.library.report(report['id'])['freshness']['state'], 'new_activity')

    def test_preview_reuses_unchanged_snapshot_and_preserves_versions(self):
        first=self.complete();second=self.complete();self.assertEqual(first['id'],second['id'])
        before=Path(first['json_path']).read_bytes()
        with self.log.open('a') as stream:stream.write('\n')
        third=self.complete();self.assertNotEqual(first['id'],third['id'])
        self.assertEqual(Path(first['json_path']).read_bytes(),before)
        self.assertFalse(self.library.report(first['id'])['source_changed']) # blank lines are not session activity
        self.assertFalse(self.library.report(third['id'])['source_changed'])
        reopened=SessionLibrary(self.logs,self.root/'library',sys.executable)
        self.assertEqual(len(reopened.state['reports']),2)

    def test_explicit_report_import_preserves_saved_prose_without_html_execution(self):
        report=self.complete();data=json.loads(Path(report['json_path']).read_text())
        data['investigation']['summary']='Saved wording <script>alert(1)</script> remains unchanged.'
        folder=self.root/'previous';folder.mkdir()
        (folder/'claude-investigation.json').write_text(json.dumps(data))
        (folder/'claude-investigation.html').write_text('<script>throw "Do not execute"</script>')
        lib=SessionLibrary(self.logs,self.root/'other-library',reports=[folder])
        saved=lib.state['reports'][0]
        self.assertEqual(json.loads(Path(saved['json_path']).read_text()),data)
        html=Path(saved['html_path']).read_text()
        self.assertNotIn('Do not execute',html);self.assertIn('&lt;script&gt;',html)
        self.assertFalse(lib.report(saved['id'])['source_changed']) # importer payload identities are comparable across stores

    def save_analysis(self, status='completed', day=1):
        preview=self.complete();data=json.loads(Path(preview['json_path']).read_text())
        data['investigation'].update(run_status=status, created_at=f'2026-10-{day:02}T12:00:00+00:00',
                                     finished_at=f'2026-10-{day:02}T12:01:00+00:00', title='Synthetic saved analysis')
        folder=self.root/('saved-'+str(len(self.library.state['reports'])));folder.mkdir()
        (folder/'report.json').write_text(json.dumps(data));(folder/'report.html').write_text(render_report(data))
        return self.library.register_report(folder/'report.json',folder/'report.html',self.item['id'],None,'investigate')

    def test_one_session_latest_analysis_not_latest_import_or_preview(self):
        first=self.save_analysis(day=4);before=Path(first['json_path']).read_bytes()
        second=self.save_analysis('partial',day=5)
        self.save_analysis(day=3) # imported later, actually older
        snapshot=self.library.snapshot()
        self.assertEqual(len(snapshot['sessions']),1)
        self.assertEqual(len(snapshot['reports']),1)
        self.assertEqual(snapshot['sessions'][0]['latest_report']['id'],second['id'])
        self.assertEqual(snapshot['sessions'][0]['states'][0]['label'],'Analysis incomplete')
        self.assertEqual(Path(first['json_path']).read_bytes(),before)
        # Same native identity and full cwd, exported under a new name: one entry.
        shutil.copyfile(self.log,self.log.parent/'renamed-export.jsonl')
        self.library.refresh();self.assertEqual(len(self.library.catalog),1)
        self.assertEqual(self.library.snapshot()['sessions'][0]['latest_report']['id'],second['id'])

    def test_freshness_ignores_mtime_and_detects_same_size_rewrite(self):
        saved=self.save_analysis();self.assertEqual(self.library.snapshot()['sessions'][0]['states'][0]['label'],'Ready')
        stamp=self.log.stat();os.utime(self.log,None)
        self.assertFalse(self.library.report(saved['id'])['source_changed'])
        text=self.log.read_text().replace('Explain what changed.','Explain what changed!')
        self.log.write_text(text);os.utime(self.log,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
        self.assertEqual(self.library.report(saved['id'])['freshness']['state'],'changed')

    def test_new_activity_does_not_hide_incompleteness_or_invalid_input(self):
        saved=self.save_analysis('partial')
        row={'type':'user','sessionId':'session-a','uuid':'new-request','timestamp':'2026-10-15T20:00:00Z','message':{'role':'user','content':'Synthetic new request.'}}
        with self.log.open('a') as f:f.write(json.dumps(row)+'\n')
        snap=self.library.refresh()['sessions'][0]
        self.assertEqual([s['key'] for s in snap['states']],['new_activity','incomplete'])
        # Malformed records cannot be classified as new activity.
        self.log.write_text('not json\n')
        self.assertNotEqual(self.library.report(saved['id'])['freshness']['state'],'current')

    def test_saved_title_activity_and_full_path_identity(self):
        rows=session_rows()+[{'type':'custom-title','sessionId':'session-a','customTitle':'Synthetic same title'}]
        rows[0]['cwd']='/north/tools/export';write_log(self.log,rows)
        other=copy.deepcopy(rows);other[0]['cwd']='/south/tools/export'
        for row in other:row['sessionId']='session-b'
        write_log(self.logs/'other'/'session-b.jsonl',other)
        items=self.library.refresh()['sessions'];self.assertEqual(len(items),2)
        self.assertEqual({i['folder_label'] for i in items},{'tools/export'})
        self.assertEqual({i['title'] for i in items},{'Synthetic same title'})
        self.assertEqual(len({i['id'] for i in items}),2)
        self.assertTrue(all(i['activity_at'] for i in items))

    def test_failed_update_retains_report_and_duplicate_job_is_blocked(self):
        saved=self.save_analysis()
        entered,release=threading.Event(),threading.Event()
        def failed_host(*args,**kwargs):
            entered.set();release.wait(5)
            class Process:
                def wait(self):return 1
            return Process()
        with patch('ally_analyzer.session_library.subprocess.Popen',side_effect=failed_host):
            self.library.start({'session':self.item['id'],'action':'investigate','allow_content':True})
            self.assertTrue(entered.wait(5))
            self.assertEqual(self.library.snapshot()['sessions'][0]['states'][0]['key'],'updating')
            with self.assertRaisesRegex(AnalyzerError,'already running'):
                self.library.start({'session':self.item['id'],'action':'investigate','allow_content':True})
            release.set();self.library.worker.join(5)
        item=self.library.snapshot()['sessions'][0]
        self.assertEqual(item['latest_report']['id'],saved['id'])
        self.assertEqual(item['states'][0]['key'],'update_failed')
        self.assertNotIn('ready',[s['key'] for s in item['states']])

    def test_unknown_report_and_permission_denials_do_not_imply_task_success(self):
        self.assertEqual(navigation_status(None,{'state':'not_analyzed'})[0]['label'],'Not analyzed')
        report={'kind':'investigate','status':'completed'}
        self.assertEqual(navigation_status(report,{'state':'unknown'})[0]['label'],'Freshness unknown')
        report['status']='unrecognized'
        self.assertEqual(navigation_status(report,{'state':'current'})[0]['label'],'Analysis state unknown')

    def test_embedded_report_keeps_saved_data_and_findings_controls(self):
        saved=self.save_analysis();data=json.loads(Path(saved['json_path']).read_text())
        html=self.library.embedded_report(saved).decode()
        self.assertIn('class="library-embedded"',html)
        self.assertIn('href="#findings-heading"',html)
        import re
        payload=json.loads(re.search(r'<script type="application/json" id="report-data">(.*?)</script>',html,re.S).group(1))
        self.assertEqual(payload,data)

    def test_child_metadata_and_later_missing_trace_use_captured_identities(self):
        from tests.test_session_agents import linked_fixture
        from tests.helpers import response
        path=linked_fixture(self.root/'linked')
        lib=SessionLibrary(path.parent,self.root/'linked-library',sys.executable)
        item=next(iter(lib.catalog.values()))
        lib.start({'session':item['id'],'action':'preview'});lib.worker.join(10)
        report=lib.latest_report(item)
        self.assertEqual(lib.freshness(item,report)['state'],'current')
        self.assertTrue(report['revision']['auxiliary'])
        # Unlinked child output is not silently added to the captured scope.
        unlinked=path.parent/'session-a/subagents/agent-unlinked.jsonl'
        write_log(unlinked,[response(88)])
        self.assertEqual(lib.freshness(item,report)['state'],'current')
        # A previously evidenced missing child becomes available.
        write_log(path.parent/'session-a/subagents/agent-missing.jsonl',[response(89)])
        self.assertEqual(lib.freshness(item,report)['state'],'new_activity')
        meta=path.parent/'session-a/subagents/agent-child-a.meta.json'
        meta.write_text(json.dumps({'toolUseId':'tool-1','agentType':'different-role'}))
        self.assertEqual(lib.freshness(item,report)['state'],'changed')
        historical=copy.deepcopy(report);historical['revision']['auxiliary']=None
        self.assertEqual(lib.freshness(item,historical)['state'],'unknown')

    def test_invalid_or_wrong_session_update_cannot_displace_saved_report(self):
        saved=self.save_analysis();before=len(self.library.state['reports'])
        data=json.loads(Path(saved['json_path']).read_text())
        target=self.root/'bad.json'
        data['investigation']['root_session_id']='different-session'
        target.write_text(json.dumps(data))
        with self.assertRaisesRegex(AnalyzerError,'different session'):
            self.library.register_report(target,Path(saved['html_path']),self.item['id'],None,'investigate')
        data['investigation']['root_session_id']=self.item['session_id']
        data['report_version']='unknown-format';target.write_text(json.dumps(data))
        with self.assertRaisesRegex(AnalyzerError,'unsupported report'):
            self.library.register_report(target,Path(saved['html_path']),self.item['id'],None,'investigate')
        self.assertEqual(len(self.library.state['reports']),before)
        self.assertEqual(self.library.latest_report(self.item)['id'],saved['id'])

    def test_disclosure_and_limits_and_closed_stdin(self):
        for options in ({}, {'allow_content':True,'budget':float('nan')}, {'allow_content':True,'timeout':0}):
            with self.assertRaises(AnalyzerError):self.library.start(dict(session=self.item['id'],action='investigate',**options))
        original=self.complete();data=json.loads(Path(original['json_path']).read_text())
        data['investigation']['run_status']='partial'
        calls=[]
        def host(command,**kwargs):
            calls.append((command,kwargs));out=Path(command[command.index('--work-dir')+1]);out.mkdir()
            (out/'claude-investigation.json').write_text(json.dumps(data))
            shutil.copyfile(original['html_path'],out/'claude-investigation.html')
            class Process:
                def wait(self):return 1
            return Process()
        with patch('ally_analyzer.session_library.subprocess.Popen',side_effect=host):
            saved=self.complete('investigate',allow_content=True,budget=2,timeout=60)
        self.assertEqual(saved['status'],'partial')
        self.assertEqual(calls[0][1]['stdin'],-3) # subprocess.DEVNULL
        self.assertNotIn('shell',calls[0][1])
        self.assertIn('--allow-content',calls[0][0])
        self.assertEqual(self.library.state['jobs'][-1]['exit_code'],1)

    def test_replaced_symlink_is_rejected(self):
        self.log.unlink();self.log.symlink_to(write_log(self.root/'outside.jsonl',session_rows()))
        with self.assertRaises(AnalyzerError):self.library.start({'session':self.item['id'],'action':'preview'})

    def test_http_boundary_and_report_routes(self):
        report=self.complete();server,url=make_server(self.library)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        origin=url.split('/library/')[0];token=url.split('/')[4]
        def get(path,**headers):
            return urllib.request.urlopen(urllib.request.Request(url+path,headers=headers),timeout=5)
        with get('api/catalog') as response:
            self.assertEqual(json.load(response)['sessions'][0]['id'],self.item['id'])
        with get('reports/'+report['id']+'.html') as response:self.assertIn(b'Investigation not run',response.read())
        with get('downloads/'+report['id']+'.json') as response:
            self.assertIn('attachment;',response.headers['Content-Disposition'])
            self.assertEqual(response.read(),Path(report['json_path']).read_bytes())
        with get('downloads/'+report['id']+'.md') as response:
            self.assertEqual(response.headers['Content-Type'],'text/markdown; charset=utf-8')
            self.assertIn('.md"',response.headers['Content-Disposition'])
            self.assertEqual(response.read(),render_markdown(json.loads(Path(report['json_path']).read_text())).encode())
        historical_html=Path(report['html_path'])
        historical_html.write_text('<!doctype html><title>Synthetic historical rendering</title>')
        with get('downloads/'+report['id']+'.html') as response:
            downloaded=response.read()
            self.assertEqual(downloaded,render_report(json.loads(Path(report['json_path']).read_text())).encode())
            self.assertNotIn(b'library-embedded',downloaded.split(b'<body')[1].split(b'>')[0])
        self.assertEqual(historical_html.read_text(),'<!doctype html><title>Synthetic historical rendering</title>')
        for path in ('../library.json','reports/../../library.json','api/report/unknown'):
            with self.assertRaises(urllib.error.HTTPError):get(path)
        with self.assertRaises(urllib.error.HTTPError):get('api/catalog',Host='example.com')
        for headers in ({},{'Origin':'https://example.com','X-Ally-Library':token}):
            with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(urllib.request.Request(url+'api/start',data=b'{}',headers=headers),timeout=5)
        request=urllib.request.Request(url+'api/start',data=json.dumps({'session':self.item['id'],'action':'preview'}).encode(),headers={'Origin':origin,'X-Ally-Library':token})
        with urllib.request.urlopen(request,timeout=5) as response:self.assertEqual(json.load(response)['report_id'],report['id'])


if __name__=='__main__':unittest.main()
