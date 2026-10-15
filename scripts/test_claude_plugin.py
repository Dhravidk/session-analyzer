#!/usr/bin/env python3
"""Opt-in live Claude Code test using only a public synthetic fixture.

Requires an already installed and authenticated Claude CLI. Runs its real
plugin loader and MCP client. Does not send the supplied Ally logs to a model.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent


def main():
    p=argparse.ArgumentParser();p.add_argument('--claude',default='claude');p.add_argument('--timeout',type=int,default=180)
    p.add_argument('--plugin',default=str(ROOT),help='Plugin directory or packaged ZIP')
    args=p.parse_args();parent=ROOT/'.analysis'/'claude-smoke';parent.mkdir(parents=True,exist_ok=True)
    os.umask(0o077)
    work=Path(tempfile.mkdtemp(prefix='run-',dir=parent))
    env=dict(os.environ,ALLY_ANALYZER_HOME=str(work/'store'))
    env.pop('ALLY_ANALYZER_ALLOW_CONTENT',None)
    prompt=("Test the ally-session-analyzer plugin using only its MCP tools. Do not use other tools. "
            "Call get_definitions, import_bundle with path "+str(ROOT/'tests/fixtures/smoke.jsonl')+" and namespace claude-smoke, "
            "poll get_job to completion, analyze_batch and poll, then get_summary and get_findings. "
            "Use the returned computed metrics. Conclude with model_responses, tools_requested, output_tokens, "
            "thinking_tokens and which rules fired. Do not request transcript content. No report export needed.")
    command=[args.claude,'--plugin-dir',str(Path(args.plugin).resolve()),'--setting-sources','', '--tools','',
             '--allowedTools','mcp__plugin_ally-session-analyzer_ally-session-analyzer__*',
             '--permission-mode','dontAsk','--model','sonnet','--effort','low','--max-budget-usd','1',
             '--no-session-persistence','--output-format','stream-json','--verbose','-p',prompt]
    with (work/'transcript.jsonl').open('w') as out,(work/'stderr.log').open('w') as err:
        result=subprocess.run(command,cwd=work,env=env,stdout=out,stderr=err,timeout=args.timeout)
    rows=[]
    for line in (work/'transcript.jsonl').read_text().splitlines():
        try:rows.append(json.loads(line))
        except ValueError:pass
    tools=[];computed=[];init=[];final=[]
    for r in rows:
        if r.get('type')=='system' and r.get('subtype')=='init':init.append({k:r.get(k) for k in ('mcp_servers','plugins','skills')})
        if r.get('type')=='result':final.append({k:r.get(k) for k in ('subtype','is_error','result','num_turns','total_cost_usd','permission_denials')})
        m=r.get('message',{})
        for b in m.get('content',[]) if isinstance(m,dict) and isinstance(m.get('content'),list) else []:
            if not isinstance(b,dict):continue
            if b.get('type')=='tool_use':tools.append(b.get('name'))
            if b.get('type')=='tool_result':
                content=b.get('content',[])
                candidates=[content] if isinstance(content,str) else [x.get('text','') for x in content if isinstance(x,dict)] if isinstance(content,list) else []
                for text in candidates:
                    try:
                        payload=json.loads(text)
                        if isinstance(payload,dict) and 'metrics' in payload:computed.append(payload)
                    except ValueError:pass
    expected={'model_responses':5,'tools_requested':4,'output_tokens':210,'thinking_tokens':58}
    metrics_ok=any(all(x.get('metrics',{}).get(k,{}).get('value')==v for k,v in expected.items()) for x in computed)
    connected=any(s.get('status')=='connected' and 'ally-session-analyzer' in s.get('name','') for i in init for s in (i.get('mcp_servers') or []))
    successful=bool(result.returncode==0 and final and not final[-1].get('is_error') and metrics_ok and connected)
    evidence={'passed':successful,'exit_code':result.returncode,'plugin_init':init,'tool_calls':tools,'expected_metrics':expected,
              'computed_metrics_verified':metrics_ok,'final':final,'fixture':'tests/fixtures/smoke.jsonl',
              'private_sources_sent':False,'transcript':str(work/'transcript.jsonl')}
    (work/'result.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence,indent=2))
    return 0 if successful else 1


if __name__=='__main__':raise SystemExit(main())
