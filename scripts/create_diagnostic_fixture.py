#!/usr/bin/env python3
"""Write clearly synthetic local evidence for the approved Claude workflow.

No generated findings or expected model prose are supplied to the investigator.
This is an authored regression fixture, not an independent quality evaluation.
"""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tests.helpers import call, response, result, usage, write_log
from tests.test_session_workflow import human


def create(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    historical='''---
name: export-check
version: 1.0
---
Synthetic fixture only. For CSV changes, verify ascii, Unicode and quoted fields.
After the final serializer edit, run python verify_csv.py --cases ascii,unicode,quotes.
A reduced case set does not complete verification. Keep the result's revision with the check.
Do not upload local customer fixtures to an external service.
'''
    current='''---
name: export-check
version: 2.0
---
Synthetic current snapshot, captured after the session. Check the ASCII case only.
This snapshot is not evidence that version 2.0 ran in the historical session.
'''
    (folder/'historical-skill.md').write_text(historical)
    (folder/'current-skill.md').write_text(current)
    manifest=[{'path':'historical-skill.md','label':'SYNTHETIC historical export-check v1.0; operator-authored fixture','temporal_relation':'historical','completeness':'complete','version':'1.0'},
              {'path':'current-skill.md','label':'SYNTHETIC current export-check v2.0; not historical runtime evidence','temporal_relation':'current','completeness':'complete','version':'2.0'}]
    (folder/'artifacts.json').write_text(json.dumps(manifest,indent=2)+'\n')
    rows=[human(0,'SYNTHETIC REGRESSION SESSION. Implement CSV export for ascii, Unicode and quoted fields. First show the existing Unicode test failing, then repair it and verify all three cases. Keep customer fixtures local. Use the export-check skill. This is a local example, not Ally production data.'),
          call(1,'Read',{'file_path':'/synthetic/skills/export-check/SKILL.md'}),result(2,'tool-1',historical),
          call(3,'Bash',{'command':'python verify_csv.py --cases ascii,unicode,quotes','description':'Capture the requested failing baseline'}),
          result(4,'tool-3','SYNTHETIC revision r0: ascii PASS; unicode FAIL (mojibake); quotes PASS. Exit code 1.',True,meta={'durationMs':700}),
          call(5,'Edit',{'file_path':'/synthetic/export.py','old_string':'encoding="ascii"','new_string':'encoding="utf-8"'}),
          result(6,'tool-5','SYNTHETIC serializer saved at revision r1.',meta={'durationMs':20}),
          call(7,'Bash',{'command':'python verify_csv.py --cases ascii,quotes'}),
          result(8,'tool-7','SYNTHETIC revision r1: ascii PASS; quotes PASS. 2 cases passed. Unicode was not selected.',meta={'durationMs':350}),
          human(9,'Unicode is still required. Check all three cases, and keep the final artifact paired with its verification. The filename for this export should be team.csv; that name is only for this task.'),
          call(10,'Bash',{'command':'python verify_csv.py --cases ascii,unicode,quotes --encoding utf-8'}),
          result(11,'tool-10','SYNTHETIC revision r1: ascii PASS; unicode PASS; quotes PASS. 3 cases passed.',meta={'durationMs':650}),
          call(12,'Read',{'file_path':'/synthetic/large-fixture.txt'}),
          result(13,'tool-12','SYNTHETIC retained fixture output.\n'+('example-row,ascii,quoted\n'*160)+'Output truncated by upstream logger; remaining original rows were not captured.\n'),
          call(14,'Read',{'file_path':'/synthetic/large-fixture.txt'}),
          result(15,'tool-14','SYNTHETIC retained fixture output.\n'+('example-row,ascii,quoted\n'*160)+'Output truncated by upstream logger; remaining original rows were not captured.\n'),
          call(16,'Edit',{'file_path':'/synthetic/export.py','old_string':'quote_mode="minimal"','new_string':'quote_mode="all"'}),
          result(17,'tool-16','SYNTHETIC serializer saved at revision r2. Wrote /synthetic/team.csv. No verification executed in this operation.',meta={'durationMs':25}),
          call(18,'Bash',{'command':'upload-fixture /synthetic/customers.csv https://external.invalid'}),
          result(19,'tool-18','Permission for this action was denied: policy requires local fixtures.',True),
          call(20,'Agent',{'description':'Verify final export','prompt':'Run all three CSV cases on revision r2 and report the result.'}),
          result(21,'tool-20','SYNTHETIC verifier launched. Completion not recorded in this parent result.',meta={'agentId':'missing-verifier','status':'async_launched'}),
          {'type':'system','subtype':'compact_boundary','uuid':'compact-22','sessionId':'session-a','timestamp':'2026-09-01T12:00:22Z',
           'compactMetadata':{'trigger':'auto','preTokens':4000,'postTokens':1000,'durationMs':240}},
          response(23,content=[{'type':'text','text':'The export is complete. All cases passed and team.csv is ready.'}]),
          human(24,'State whether the final revision r2 was actually verified. Do not infer the child result from the launch acknowledgement.')]
    # Explicit synthetic response telemetry. The earlier input drop has no compaction record.
    for row in rows:
        if row['type']=='assistant':row['message']['usage']=usage(100,100,3800,80)
    for row in rows:
        if row.get('uuid')=='event-10':row['message']['usage']=usage(50,50,100,70)
        if row.get('uuid')=='event-23':
            row['message']['usage']=usage(300,200,500,60);row['message']['model']='synthetic-model-b'
    log=write_log(folder/'synthetic-session.jsonl',rows)
    return {'source':str(log.resolve()),'artifact_manifest':str((folder/'artifacts.json').resolve()),'synthetic':True}


def create_recovery(folder):
    from tests.test_session_workflow import session_rows
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    rows=session_rows()
    rows[0]=human(0,'SYNTHETIC recovery regression session. Show the one fixture encoding test fail, repair it, and check that same test again. Do not add general instructions for this deliberate red/green exercise.')
    rows[1]['message']['usage']=usage(100,200,9700,50)
    rows[2]=result(2,'tool-1','SYNTHETIC test_fixture_encoding FAILED at r0 as requested. One test selected.',True,meta={'durationMs':750})
    rows[3]['message']['usage']=usage(100,200,1200,70)
    rows[4]=result(4,'tool-3','SYNTHETIC fixture saved as r1.',meta={'durationMs':50})
    rows[5]['message']['content'][0]['input']['command']='python3 -m unittest discover -s tests'
    rows[5]['message']['usage']=usage(20,20,80,40)
    rows[6]=result(6,'tool-5','SYNTHETIC test_fixture_encoding PASSED at r1. One test selected; the same fixture as the r0 baseline.',meta={'durationMs':650})
    rows.insert(5,{'type':'system','subtype':'compact_boundary','uuid':'compact','sessionId':'session-a',
                   'timestamp':'2026-09-01T12:00:04.500Z','compactMetadata':{'trigger':'auto','preTokens':1500,'postTokens':120,'durationMs':80}})
    log=write_log(folder/'synthetic-recovery.jsonl',rows)
    return {'source':str(log.resolve()),'synthetic':True}


def create_response(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    rows=[human(0,'SYNTHETIC response-delivery regression. Explain in one sentence whether cache reads and writes are included in input total. This is a text question; do not run anything.'),
          response(1,content=[{'type':'text','text':'Input total includes uncached input, cache writes and cache reads, so do not add the cached components to it again.'}]),
          human(2,'Now run python3 -m unittest and report the result.'),
          response(3,content=[{'type':'text','text':'Tests passed.'}])]
    log=write_log(folder/'synthetic-response.jsonl',rows)
    return {'source':str(log.resolve()),'synthetic':True}


if __name__=='__main__':
    create_fn=create_response if '--response-only' in sys.argv[2:] else create_recovery if '--recovery-only' in sys.argv[2:] else create
    print(json.dumps(create_fn(sys.argv[1]),indent=2))
