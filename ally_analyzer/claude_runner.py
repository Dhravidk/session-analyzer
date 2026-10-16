#!/usr/bin/env python3
"""Run the shipped single-session Claude workflow; preserve every submitted output.

Uses the operator's approved host/account and model quota. No Codex prose pass.
The final report is the standard renderer over exact persisted model submissions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import zipfile
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ally_analyzer.engine import analyze_dataset, canonical_report
from ally_analyzer.ingest import import_bundle
from ally_analyzer.mcp import SESSION_TOOLS
from ally_analyzer.session_report import export_session_investigation, report_data, render_report
from ally_analyzer.session_scope import get_run, start_session_investigation
from ally_analyzer.session_review import update_workflow, latest_draft
from ally_analyzer.store import Store
from ally_analyzer.util import canonical, utc_now

DEFAULT_QUESTION = 'Investigate the task, relevant instructions, successes and failures, later recovery and remaining useful changes. Preserve insufficient evidence and no-action conclusions when warranted.'


def parse_transcript(path):
    calls, finals, host, malformed = [], [], [], 0
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            malformed += 1; continue
        if row.get('type') == 'result': finals.append(row)
        if row.get('type') == 'system' and row.get('subtype') == 'init':
            host.append({k:row.get(k) for k in ('model','plugins','skills','mcp_servers')})
        message = row.get('message')
        blocks = message.get('content', []) if isinstance(message, dict) else []
        for block in blocks if isinstance(blocks,list) else []:
            if isinstance(block,dict) and block.get('type')=='tool_use':
                calls.append({k:block.get(k) for k in ('id','name','input')})
    return calls, finals, host, malformed


def run_host(command, work, env, timeout):
    timed_out, host_error, exit_code = False, None, None
    with (work/'transcript.jsonl').open('w') as out, (work/'stderr.log').open('w') as err:
        try:
            # Claude -p also consumes piped stdin. Only the explicit stage prompt
            # belongs to this run; a parent pipe may contain unrelated material.
            proc = subprocess.Popen(command, cwd=work, env=env, stdin=subprocess.DEVNULL,
                                    stdout=out, stderr=err, start_new_session=True)
            try:
                exit_code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                # Stop the host and its MCP descendants; never leave a timed-out writer running.
                os.killpg(proc.pid, signal.SIGTERM)
                try: proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL); proc.wait()
        except OSError as exc:
            host_error = type(exc).__name__
    return {'exit_code':exit_code, 'timed_out':timed_out, 'host_error':host_error}


def terminal_host_failure(outcome, final):
    """A fresh reviewer cannot repair a failed host or provider connection."""
    if outcome.get('host_error'):
        return {'kind':'host_setup', 'message':outcome['host_error']}
    if final.get('is_error') and (final.get('terminal_reason')=='api_error'
            or final.get('api_error_status') in (401,403)
            or str(final.get('result','')).startswith('Failed to authenticate:')):
        return {'kind':'provider_error', 'message':final.get('result') or 'The host reported an API error.',
                'api_error_status':final.get('api_error_status')}
    return None


def audit_tool_policy(calls, transcript, allowed, allowed_skills=('ally-session-analyzer:write-report',)):
    """Keep failed attempts visible; a host-rejected unknown tool did not execute."""
    def permitted(c):
        return c['name'] in allowed or (c['name']=='Skill' and isinstance(c.get('input'),dict)
                                        and c['input'].get('skill') in allowed_skills)
    undeclared = [c for c in calls if not permitted(c)]
    results = {}
    for line in transcript.read_text().splitlines():
        try: row=json.loads(line)
        except ValueError: continue
        message=row.get('message')
        for b in message.get('content',[]) if isinstance(message,dict) and isinstance(message.get('content'),list) else []:
            if isinstance(b,dict) and b.get('type')=='tool_result': results[b.get('tool_use_id')]=b
    rejected=[];unverified=[]
    for c in undeclared:
        r=results.get(c['id'],{})
        expected='<tool_use_error>Error: No such tool available: '+c['name']+'</tool_use_error>'
        entry={'call_id':c['id'],'name':c['name'],'result':r}
        (rejected if r.get('is_error') is True and r.get('content')==expected else unverified).append(entry)
    return {'allowed_calls_only':not undeclared, 'executed_calls_within_policy':not unverified,
            'rejected_unknown_tool_attempts':rejected, 'unverified_or_disallowed_calls':unverified}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True); p.add_argument('--session-id')
    p.add_argument('--work-dir', required=True, help='New private output directory')
    p.add_argument('--claude', default='claude'); p.add_argument('--plugin', default=str(ROOT))
    p.add_argument('--allow-content', action='store_true'); p.add_argument('--model', default='sonnet')
    p.add_argument('--include-source-text-in-report', action='store_true', help='Embed retained masked text in local HTML/JSON exports')
    p.add_argument('--max-budget-usd', type=float, default=3); p.add_argument('--timeout', type=int, default=600)
    p.add_argument('--question', default=DEFAULT_QUESTION)
    p.add_argument('--artifact-manifest', help='Local JSON list of explicitly selected snapshots: path, label, temporal_relation, completeness, optional version. No discovery or connector access.')
    args = p.parse_args(argv)
    os.umask(0o077)
    if args.timeout < 1 or args.max_budget_usd <= 0:
        p.error('Timeout and budget must be positive')
    if args.include_source_text_in_report and not args.allow_content:
        p.error('Embedding source text requires --allow-content')
    work = Path(args.work_dir).expanduser().resolve(); work.mkdir(parents=True, exist_ok=False, mode=0o700)
    source = Path(args.source).expanduser().resolve(strict=True)
    plugin = Path(args.plugin).expanduser().resolve(strict=True)
    if plugin.is_file():
        plugin_fingerprint = hashlib.sha256(plugin.read_bytes()).hexdigest()
        saved_plugin = work / 'tested-plugin.zip'
        shutil.copyfile(plugin, saved_plugin)
        plugin = saved_plugin
    else:
        selected_files = [plugin/'.claude-plugin/plugin.json', plugin/'.mcp.json', plugin/'bin/ally-session',
                          plugin/'scripts/ally-session.py']
        selected_files += list((plugin/'ally_analyzer').glob('*.py')) + list((plugin/'skills').glob('*/SKILL.md'))
        selected_files += [plugin/'ally_analyzer'/name for name in ('session_report.css','session_report.js',
                          'session_library.html','session_library.css','session_library.js')]
        selected_files += list((plugin/'ally_analyzer/icons').glob('*'))
        inventory = [(str(p.relative_to(plugin)), hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(selected_files)]
        (work/'plugin-inventory.json').write_text(json.dumps(inventory, indent=2))
        saved_plugin = work / 'tested-plugin.zip'
        with zipfile.ZipFile(saved_plugin, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(selected_files): archive.write(path, path.relative_to(plugin).as_posix())
        plugin = saved_plugin
        plugin_fingerprint = hashlib.sha256(plugin.read_bytes()).hexdigest()
    store = Store(work / 'store')
    imported = import_bundle(store, source, namespace='claude-single-session')
    aid = analyze_dataset(store, imported['dataset_id'])['analysis_id']
    sessions = list(store.items(aid, 'session'))
    if args.session_id:
        sid = args.session_id
    elif len(sessions) == 1:
        sid = sessions[0]['id']
    else:
        p.error('Select --session-id when an import contains more than one session')
    artifact_ids=[]
    if args.artifact_manifest:
        from ally_analyzer.session_validation import admit_artifact
        manifest_path=Path(args.artifact_manifest).expanduser().resolve(strict=True)
        snapshots=json.loads(manifest_path.read_text())
        required={'path','label','temporal_relation','completeness'}
        if not isinstance(snapshots,list) or len(snapshots)>100:
            p.error('Artifact manifest must be a list of at most 100 explicitly selected files')
        for item in snapshots:
            if not isinstance(item,dict) or required-set(item) or set(item)-required-{'version'}:
                p.error('Artifact manifest entry has missing or unsupported fields')
            path=Path(item['path']).expanduser()
            if not path.is_absolute():path=manifest_path.parent/path
            artifact_ids.append(admit_artifact(store,path.resolve(strict=True),item['label'],item['temporal_relation'],item['completeness'],item.get('version'))['id'])
        (work/'artifact-manifest.json').write_text(json.dumps({'source_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),'admitted_artifact_ids':artifact_ids},indent=2)+'\n')
    run = start_session_investigation(store, aid, sid, args.question, artifact_ids=artifact_ids)['investigation']
    iid = run['id']
    update_workflow(store, iid, 'investigate', requirement_mapping=True, semantic_consistency=True, citation_explanations=True, reader_guides=True)
    before = hashlib.sha256(canonical(canonical_report(store, aid)).encode()).hexdigest()
    prompt = ('/ally-session-analyzer:investigate ' + iid + '\n' + args.question + '\n'
              'This host is bound to the selected investigation. Use only the analyzer tools and the packaged writing skill. '
              'Read relevant retained evidence, save incidents and only justified optional recommendations, and finish_investigation. '
              'The runner will export every saved candidate and your exact final output using the standard renderer when this host ends. '
              'Do not depend on an external editor. Do not apply suggested changes. ')
    if args.question == DEFAULT_QUESTION:
        prompt += 'No topic, event or conclusion anchors were selected for you.'
    if args.allow_content:
        prompt += ' The operator authorizes controlled excerpts through this approved Claude host.'
    (work / 'request.txt').write_text(prompt)
    names = [t['name'] for t in SESSION_TOOLS if t['name'] != 'start_session_investigation'] + ['get_definitions', 'get_session_guide']
    allowed = ['mcp__plugin_ally-session-analyzer_ally-session-analyzer__' + name for name in names]
    env = dict(os.environ, ALLY_ANALYZER_HOME=str(store.root), ALLY_ANALYZER_ALLOW_CONTENT='1' if args.allow_content else '0',
               ALLY_ANALYZER_SESSION_ONLY='1', ALLY_ANALYZER_INVESTIGATION_ID=iid)
    started = time.monotonic()
    calls, finals, host, stages = [], [], [], []
    spent = 0.0
    for phase in ('investigate', 'review', 'review_continue'):
        remaining_time = args.timeout - (time.monotonic() - started)
        remaining_budget = args.max_budget_usd - spent
        if remaining_time <= 1 or remaining_budget <= 0:
            break
        if phase != 'investigate':
            if get_run(store,iid)['run_status'] not in ('created','running'): break
            if phase == 'review': update_workflow(store, iid, 'review')
            stage_prompt = ('/ally-session-analyzer:review ' + iid + '\n'
                            'Review the saved investigation in a fresh context using the packaged review procedure. '
                            'Use get_investigation_review to recover the draft and evidence plan. Continue unfinished material inquiry, '
                            'correct unsupported statements through immutable revisions, and finalize only after source-backed review. '
                            'Map all main-session user requests and investigate the remaining material questions. A partial checkpoint is preserved; '
                            'continue it while evidence and host budget remain. Completing inquiry does not require reading every assistant step or inventing missing evidence. '
                            'No topic, expected diagnosis, or desired conclusion is supplied. The scope and disclosure permission are unchanged.')
        else:
            stage_prompt = prompt
        stage_dir = work / phase
        stage_dir.mkdir(mode=0o700)
        (stage_dir/'request.txt').write_text(stage_prompt)
        budget = remaining_budget * 0.60 if phase == 'investigate' else remaining_budget
        timeout = remaining_time * 0.60 if phase == 'investigate' else remaining_time
        command = [args.claude, '--plugin-dir', str(plugin), '--setting-sources', '', '--tools', 'Skill',
                   '--allowedTools', *allowed, 'Skill(ally-session-analyzer:write-report)', '--permission-mode', 'dontAsk',
                   '--model', args.model, '--effort', 'medium' if phase == 'investigate' else 'high',
                   '--max-budget-usd', str(budget), '--no-session-persistence', '--output-format', 'stream-json',
                   '--verbose', '-p', stage_prompt]
        outcome = run_host(command, stage_dir, env, timeout)
        stage_calls, stage_finals, stage_host, malformed = parse_transcript(stage_dir/'transcript.jsonl')
        failure = terminal_host_failure(outcome, stage_finals[-1] if stage_finals else {})
        cost = stage_finals[-1].get('total_cost_usd') if stage_finals else None
        # Missing usage cannot be treated as zero when allocating the second host.
        spent += cost if isinstance(cost, (int,float)) else budget
        calls += stage_calls; finals += stage_finals; host += stage_host
        stages.append(dict(phase=phase, budget_usd=budget, timeout_seconds=timeout,
                           cost_usd=cost, host=stage_host, final=stage_finals, terminal_failure=failure,
                           malformed_stream_lines=malformed, **outcome))
        if stage_finals: (stage_dir/'claude-answer.md').write_text(stage_finals[-1].get('result',''))
        (stage_dir/'host-audit.json').write_text(json.dumps(stages[-1],indent=2)+'\n')
        # A failed executable/setup cannot be repaired by launching a second copy.
        if failure or (not stage_host and not stage_finals): break
    (work/'transcript.jsonl').write_bytes(b''.join((work/s['phase']/'transcript.jsonl').read_bytes() for s in stages))
    (work/'stderr.log').write_bytes(b''.join((work/s['phase']/'stderr.log').read_bytes() for s in stages))
    final = finals[-1] if finals else {}
    last = stages[-1] if stages else {}
    timed_out = any(s['timed_out'] for s in stages)
    host_error, exit_code = last.get('host_error'), last.get('exit_code')
    malformed = sum(s['malformed_stream_lines'] for s in stages)
    run = get_run(store, iid)
    run['provenance']['runner_attestation'] = {'host_init': host, 'runner': 'claude-runner-v5', 'captured_at': utc_now(),
                                              'transcript_sha256': hashlib.sha256((work / 'transcript.jsonl').read_bytes()).hexdigest(),
                                              'plugin_sha256': plugin_fingerprint, 'plugin_snapshot': str(plugin), 'stages':stages}
    run['analyzer_usage'] = {'status': 'host_reported' if all(s['cost_usd'] is not None for s in stages) else 'partial',
                            'usage': [{'phase':s['phase'],'usage':s['final'][-1].get('usage') if s['final'] else None} for s in stages],
                            'model_usage': [{'phase':s['phase'],'models':s['final'][-1].get('modelUsage') if s['final'] else None} for s in stages],
                            'cost_usd': sum(s['cost_usd'] for s in stages) if all(s['cost_usd'] is not None for s in stages) else None,
                            'tool_calls': len(calls), 'elapsed_seconds': time.monotonic() - started,
                            'source_session_usage_included': False}
    failure = last.get('terminal_failure')
    run['host_outcome'] = {'exit_code': exit_code, 'timed_out': timed_out, 'host_error': host_error, 'terminal_failure':failure,
                           'result_subtype': final.get('subtype'), 'is_error': final.get('is_error'), 'malformed_stream_lines': malformed}
    policy = audit_tool_policy(calls,work/'transcript.jsonl',allowed)
    run['host_outcome'].update(policy)
    if run['run_status'] in ('created','running'):
        run['run_status'] = 'failed' if failure else 'partial'
        run['stop_reason'] = 'Host could not continue: '+failure['message'] if failure else 'Host ended without a saved investigation conclusion'
        run['runner_unresolved_question'] = 'The declared investigation and source-backed review procedure was not finished by the host.'
        run['unfinished_draft'] = latest_draft(store, iid)
        run['stop_basis'] = 'external_limit' if failure or timed_out or any(f.get('subtype')=='error_max_budget_usd' for f in finals) else 'investigator_choice'
    with store.connect() as db:
        db.execute('UPDATE session_runs SET payload=? WHERE id=?', (canonical(run), iid))
    export_options = {'include_source_text':args.include_source_text_in_report,'allow_content':args.allow_content}
    exported = export_session_investigation(store, iid, work / 'claude-investigation.json', 'json', **export_options)
    export_session_investigation(store, iid, work / 'claude-investigation.html', **export_options)
    data = json.loads(Path(exported['path']).read_text())
    def submitted(name, field):
        return [c['input'].get(field) for c in calls if c['name'].endswith('__' + name)]
    exact_incidents = all(r['incident'] in submitted('save_incident','incident') for r in data['incident_history'])
    exact_proposals = all(r['recommendation'] in submitted('save_recommendation','recommendation') for r in data['recommendations'])
    finishes = [c['input'] for c in calls if c['name'].endswith('__finish_investigation')]
    exact_synopsis = not run.get('synopsis') or any(run['synopsis'] == f.get('synopsis') for f in finishes)
    exact_inquiries = all(r['inquiry'] in submitted('save_inquiry','inquiry') for r in data.get('inquiries',[]))
    exact_maps = all(r['requirement_map'] in submitted('save_requirement_map','requirement_map') for r in data.get('requirement_map_history',[]))
    exact_failures = all(r['explanation'] in submitted('save_failure_explanation','explanation') for r in data.get('failure_explanations',[]))
    review_inputs = [check for c in calls if c['name'].endswith('__save_review_checks') for check in c['input']['checks']]
    exact_reviews = all(r['check'] in review_inputs for r in data.get('review_checks',[]))
    exact_drafts = all(any(r['conclusion'] == {k:v for k,v in f.items() if k!='investigation_id'} for f in finishes) for r in data.get('conclusion_drafts',[]))
    exact_report = (work / 'claude-investigation.html').read_bytes() == render_report(data).encode()
    unchanged = before == hashlib.sha256(canonical(canonical_report(store, aid)).encode()).hexdigest()
    loaded = any(c['name']=='Skill' and c['input'].get('skill')=='ally-session-analyzer:write-report' for c in calls)
    allowed_only = policy['allowed_calls_only']
    transport = exact_incidents and exact_proposals and exact_synopsis and exact_inquiries and exact_maps and exact_failures and exact_reviews and exact_drafts and exact_report and unchanged and policy['executed_calls_within_policy']
    completed = run['run_status']=='completed' and last.get('phase') in ('review','review_continue') and bool(finals) and not final.get('is_error') and exit_code==0
    audit = {'origin_and_transport_checks_passed': transport, 'host_completed_investigation': completed, 'writing_skill_invoked': loaded,
             'analysis_id': aid, 'investigation_id': iid, 'run_status': run['run_status'], 'conclusion': run['conclusion'],
             'saved_incidents':len(data['incidents']), 'saved_recommendations':len(data['recommendations']),
             'recommendations_match_claude_tool_inputs':exact_proposals, 'incidents_match_claude_tool_inputs':exact_incidents,
             'synopsis_matches_claude_tool_input':exact_synopsis, 'inquiries_match_claude_tool_inputs':exact_inquiries,
             'requirement_maps_match_claude_tool_inputs':exact_maps,
             'failure_explanations_match_claude_tool_inputs':exact_failures,
             'review_checks_match_claude_tool_inputs':exact_reviews, 'conclusion_drafts_match_claude_tool_inputs':exact_drafts,
             'independent_review_host_started':any(s['phase']=='review' for s in stages), 'stages':stages,
             'failure_explanation_coverage':data.get('failure_explanation_coverage'),
             'html_matches_standard_export':exact_report, 'canonical_analysis_unchanged':unchanged, 'allowed_calls_only':allowed_only,
             'tool_policy':policy,
             'codex_edited_recommendations':False, 'topic_anchors_supplied_by_runner':False if args.question == DEFAULT_QUESTION else None,
             'prompt_kind':'default_unanchored' if args.question == DEFAULT_QUESTION else 'operator_supplied_question_not_certified_unanchored',
             'report':str(work / 'claude-investigation.html'), 'host':host, 'calls':calls, 'final':finals,
             'limitation':'Transport checks do not establish semantic quality or superiority. Partial and unsuccessful runs are retained.'}
    (work / 'audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    if finals: (work / 'claude-answer.md').write_text(final.get('result',''))
    print(json.dumps({k:v for k,v in audit.items() if k not in ('host','calls','final','stages')},indent=2))
    return 0 if completed and loaded and transport else 1


if __name__=='__main__': raise SystemExit(main())
