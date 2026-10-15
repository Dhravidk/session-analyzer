#!/usr/bin/env python3
"""Persist synthetic boundary cases through the real APIs; never production analysis."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tests.test_session_diagnostics import DiagnosticTests
from tests.test_session_workflow import human, session_rows
from ally_analyzer.session_diagnostics import save_inquiry
from ally_analyzer.session_investigation import save_incident, save_recommendation
from ally_analyzer.session_report import export_session_investigation


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    manifest=[]
    for case in ('edits','long-missing','no-action','insufficient','partial','not-run'):
        ctx=DiagnosticTests();ctx.setUp()
        try:
            if case=='long-missing':
                rows=session_rows();rows[0]=human(0,'Please repair the fixture while preserving this original request.\n'+('A long request retains every detail, including quotes, <tags>, newlines and Unicode 😀.\n'*60)+'END_OF_LONG_REQUEST')
                rows[1]['message'].pop('usage');ctx.load(rows)
            if case=='edits':
                exact='Run `python -m unittest`.\nPreserve "quotes", $() and <tags> literally. 😀\n'
                proposal=ctx.instruction(replacement=exact)
                proposal['title']='Synthetic QA: replace one command'
                save_recommendation(ctx.store,ctx.iid,proposal)
                invoked=json.loads(json.dumps(proposal));invoked['title']='Synthetic QA: use the existing fixture skill';invoked['target_kind']='use_existing_skill'
                invoked['edit']={k:v for k,v in proposal['edit'].items() if k not in ('original_text','replacement_text')}
                invoked['edit'].update(operation='invoke',invocation='/check-fixture')
                save_recommendation(ctx.store,ctx.iid,invoked)
                save_incident(ctx.store,ctx.iid,ctx.incident(title='Synthetic QA: a second finding in the same turn'))
                (out/'copy-expectation.txt').write_text(exact)
            if case!='not-run':
                ctx.read_all()
                if case=='partial':
                    save_inquiry(ctx.store,ctx.iid,ctx.inquiry(status='open',answer='Available evidence remains to be investigated.',next_source_ids=[ctx.ids['event-6']]))
                    ctx.finish(title='Synthetic QA: incomplete investigation',run_status='partial',stop_basis='investigator_choice',unresolved_questions=['Available result remains uninvestigated.'])
                elif case=='insufficient':
                    save_inquiry(ctx.store,ctx.iid,ctx.inquiry(status='unavailable',answer='Deployment outcome was not captured.',references=[],missing_evidence=['Deployment result.']))
                    ctx.finish(title='Synthetic QA: insufficient evidence',conclusion='insufficient_evidence',stop_basis='evidence_unavailable',unresolved_questions=['Deployment result not captured.'])
                else:
                    save_inquiry(ctx.store,ctx.iid,ctx.inquiry())
                    ctx.finish(title='Synthetic QA: '+case,conclusion='findings' if case=='edits' else 'no_action_supported')
            paths=[]
            for fmt in ('html','json'):
                paths.append(export_session_investigation(ctx.store,ctx.iid,out/(case+'.'+fmt),fmt,include_source_text=True,allow_content=True))
            manifest.append({'case':case,'exports':paths})
        finally:ctx.doCleanups()
    (out/'manifest.json').write_text(json.dumps({'synthetic':True,'purpose':'Renderer interaction and boundary tests, not model quality evidence','cases':manifest},indent=2)+'\n')
    print(out.resolve())

if __name__=='__main__':main()
