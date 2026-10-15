"""Offline document renderer. Authored text is escaped, never rewritten or ranked."""
import base64
from collections import defaultdict
from datetime import datetime
import hashlib
import html
import json
import re
from pathlib import Path

from .session_diagnostics import record_role, coverage_assertions
from .session_edits import inspect_edit
from .session_agents import build_agent_views
from .session_failures import active_explanations, failure_coverage
from .session_review import active_versions
from .session_investigation import accounting, records
from .session_patterns import RECORDED_FAILURE_OUTCOMES, turn_patterns
from .session_scope import entities, exposure, get_run, get_scope, projection, scope_rows, source_record
from .session_validation import get_validation_results
from .trajectory import require_content, trajectory_text
from .source_content import source_content
from .session_reading import (REQUIREMENT_STATUS, requirement_anchor, requirement_refs,
                              related_turns, remaining_items, remaining_work_text)
from .util import AnalyzerError, canonical, digest, strict_json

# A long-lived host must render one immutable asset version. Reading assets on
# every export could mix revisions if deployment changes files between exports.
REPORT_CSS = Path(__file__).with_name('session_report.css').read_text()
REPORT_JS = Path(__file__).with_name('session_report.js').read_text()
REPORT_ICONS = {p.stem:base64.b64encode(p.read_bytes()).decode()
                for p in sorted(Path(__file__).with_name('icons').glob('*.svg'))}
REPORT_WRAP_ICONS = {name:base64.b64encode(Path(__file__).with_name('icons').joinpath(name+'.png').read_bytes()).decode()
                     for name in ('word-wrap-off','word-wrap-on')}
REPORT_ICON_LICENSE = Path(__file__).with_name('icons').joinpath('LICENSE').read_text()


def report_data(store, investigation_id, include_source_text=False, allow_content=False):
    if include_source_text:
        require_content(allow_content)
    run = get_run(store, investigation_id)
    scope = get_scope(store, run)
    from .session_navigation import auxiliary_key
    # Importer-owned hashes of structural child metadata, not model assertions.
    with store.connect() as db:
        auxiliary = {auxiliary_key(r['path']): r['sha256'] for r in db.execute(
            'SELECT path,sha256 FROM files WHERE dataset_id=?', (scope['dataset_id'],))
            if r['path'].endswith('.meta.json') and (scope['root_session_id']+'/subagents/') in r['path']}
    proposals = records(store, investigation_id, 'recommendation')
    metrics = accounting(store, run)
    tools, rows = entities(store, run, 'tool'), scope_rows(store, run)
    agent_views = build_agent_views(store,run,metrics)
    from .session_requirements import current_map
    from .session_resources import context_timeline, tool_output_index
    from .session_episodes import episode_resources
    incidents=active_versions(records(store,investigation_id,'incident'),'incident')
    resources={aid:{'context':context_timeline(store,run,aid),
                    'outputs':tool_output_index(store,run,aid,inspect_markers=include_source_text)}
               for aid,a in agent_views['agents'].items() if a['trace_status']=='captured'}
    if include_source_text:
        by_id={r['id']:r for r in rows}
        for invocation in agent_views['delegations']:
            raw=strict_json(by_id[invocation['invocation_source_id']]['raw'])
            from .normalize import content_blocks
            for block in content_blocks(raw):
                if block.get('type')!='tool_use' or block.get('id')!=invocation['tool_id']:continue
                arguments=block.get('input',{})
                for field,key in (('description','label'),('prompt','task_text')):
                    if isinstance(arguments,dict) and isinstance(arguments.get(field),str):
                        text,_=trajectory_text({'message':{'content':arguments[field]}},scope['text_version'])
                        invocation[key]=text
    sources, agents, raw_records = {}, defaultdict(list), {}
    # Export is a local reading surface. It must not inflate Claude's exposure log.
    with store.connect() as db:
        for row in rows:
            item = {k:row[k] for k in ('id','kind','agent_id','timestamp','payload_hash')}
            raw = strict_json(row['raw'])
            raw_records[row['id']] = raw
            item['role'] = record_role(raw, row['kind'])
            item['content_metadata'] = source_content(raw, include_thinking_text=include_source_text)
            item['source_refs'] = [{'member_id':digest(r['path'])[:16], 'line':r['line']} for r in db.execute(
                'SELECT path,line FROM provenance WHERE dataset_id=? AND event_id=? ORDER BY path,line', (scope['dataset_id'],row['id']))]
            sources[row['id']] = item
            agents[row['agent_id']].append(row['id'])
        for sid in scope['artifact_ids']:
            sources[sid] = {'id':sid,'role':'artifact','kind':'artifact','metadata':source_record(store,run,sid)['metadata']}
        if include_source_text:
            for sid, item in sources.items():
                text, sha, disclosure, _ = projection(store,run,sid,scope=scope,include_metadata=False,connection=db)
                item.update(text=text,text_sha256=sha,disclosure=disclosure)
    for ids in agents.values():
        for index, sid in enumerate(ids):
            sources[sid].update(previous=ids[index-1] if index else None, next=ids[index+1] if index+1<len(ids) else None)
    for tool in tools:
        for sid in tool['evidence']:
            sources[sid].setdefault('tool_ids', []).append(tool['id'])
    response_usage = {}
    for response in entities(store,run,'response'):
        usage = {k:response[k] for k in ('id','tokens','eligible','usage_status','evidence','warnings')}
        detail_recorded = False
        for sid in response['evidence']:
            message = raw_records.get(sid,{}).get('message')
            captured_usage = message.get('usage') if isinstance(message,dict) else None
            details = captured_usage.get('output_tokens_details') if isinstance(captured_usage,dict) else None
            if details is not None and (not isinstance(details,dict) or 'thinking_tokens' in details):
                detail_recorded = True
        usage['thinking_tokens_status'] = ('reported' if response['tokens']['thinking_tokens'] is not None else
            'unavailable' if detail_recorded or response['usage_status'] in ('missing','conflict','provisional_interrupted') else 'not_separately_reported')
        response_usage[response['id']] = usage
        for sid in response['evidence']:
            if sid in sources:
                sources[sid].setdefault('response_ids',[]).append(response['id'])
    return {'report_version':'session-investigation-v2','investigation':run,'scope':scope,
            'accounting':metrics,'turn_patterns':turn_patterns(metrics['turns'],tools), **agent_views,
            'incidents':incidents,
            'requirement_map':current_map(store,investigation_id),
            'requirement_map_history':records(store,investigation_id,'requirement_map'),
            'resource_views':resources,
            'episode_resources':{i['id']:episode_resources(store,run,[i]) for i in incidents if i['incident'].get('episode')},
            'incident_history':records(store,investigation_id,'incident'),'claims':records(store,investigation_id,'claim'),
            'measurements':records(store,investigation_id,'measurement'),'recommendations':proposals,
            'inquiries':records(store,investigation_id,'inquiry'),
            'conclusion_drafts':records(store,investigation_id,'conclusion_draft'),
            'review_checks':records(store,investigation_id,'review_check'),
            'failure_explanations':records(store,investigation_id,'failure_explanation'),
            'failure_explanation_coverage':failure_coverage(tools,records(store,investigation_id,'failure_explanation')),
            'validation':{p['id']:get_validation_results(store,investigation_id,p['id']) for p in proposals},
            'edit_inspection':{p['id']:inspect_edit(store,run,p['recommendation']) for p in proposals},
            'artifacts':[sources[aid]['metadata'] for aid in scope['artifact_ids']],
            'sources':sources,'tools':tools,'response_usage':response_usage,'source_text_included':include_source_text,
            'report_checks':coverage_assertions(scope,{k:run.get(k) for k in ('synopsis','observed_outcome','summary','coverage_explanation')}),
            'exposure':exposure(store,investigation_id),
            'source_capture':{'auxiliary_sha256':auxiliary, 'basis':'Importer file inventory; child-linkage metadata only.'},
            'rendering_contract':'Saved Claude wording is unchanged. Previews are literal prefixes. Local source exports can include captured masked thinking separately from the investigator evidence projection. Raw records remain in the local store. Exporting source text is not a model read receipt; thinking is not proof of execution.'}


def esc(value):
    return html.escape(str(value), quote=True)


def number(value):
    if value is None: return 'Unknown'
    if isinstance(value, float): return f'{value:,.2f}'.rstrip('0').rstrip('.')
    return f'{value:,}' if isinstance(value,int) else esc(value)


def compact(value):
    if value is None: return 'Unknown'
    for scale,suffix in ((1000000000,'B'),(1000000,'M'),(1000,'k')):
        if value >= scale: return f'{value/scale:.2f}'.rstrip('0').rstrip('.')+suffix
    return number(value)


def prose(value, cls='prose'):
    return '<p class="'+cls+'">'+esc(value)+'</p>'


def icon(name):
    if name in REPORT_WRAP_ICONS:
        return '<span class="wrap-symbol '+name+'" aria-hidden="true" style="--wrap-image:url(data:image/png;base64,'+REPORT_WRAP_ICONS[name]+')"></span>'
    return '<span class="icon" aria-hidden="true" style="--icon:url(data:image/svg+xml;base64,'+REPORT_ICONS[name]+')"></span>'


def command_request(source):
    """Recognize only a whole, well-formed user command envelope; never summarize it."""
    if source.get('role') != 'user_statement' or not isinstance(source.get('text'), str):
        return None
    match = re.fullmatch(
        r'\s*<command-message>([^<>]*)</command-message>\s*'
        r'<command-name>([^<>]*)</command-name>'
        r'(?:\s*<command-args>([^<>]*)</command-args>)?\s*', source['text'])
    if not match or not re.fullmatch(r'/[\w./:-]+', match[2].strip()):
        return None
    message, command, arguments = match.groups()
    # Only the exact redundant name is omitted. Different message text remains visible.
    extra = message if message.strip() not in (command.strip(), command.strip()[1:]) else None
    filename = None
    if arguments and not re.search(r'\s', arguments) and re.match(r'^(?:/|\./|\.\./|[A-Za-z]:[\\/])', arguments):
        filename = re.split(r'[\\/]', arguments)[-1] or None
    return {'command':command, 'arguments':arguments, 'message':extra, 'filename':filename}


def request_preview(source, parsed):
    if not parsed:
        text = source.get('text', 'Source text not included')
        return esc(text[:180]+('…' if len(text)>180 else ''))
    if parsed['arguments'] is not None:
        argument = parsed['filename'] or parsed['arguments'] or '(empty)'
        preview = argument[:120]+('…' if len(argument)>120 else '')
        result = '<span class="command-argument">'+(icon('file') if parsed['filename'] else '')+'<span>'+esc(preview)+'</span><span class="argument-label">Argument</span></span>'
        result += '<span class="command-label">Command</span><code class="command-name">'+esc(parsed['command'])+'</code>'
    else:
        result = '<code class="command-name">'+esc(parsed['command'])+'</code><span class="command-label">Command request</span>'
    if parsed['message']:
        text=parsed['message']
        result+='<span class="command-message">'+esc(text[:180]+('…' if len(text)>180 else ''))+'</span>'
    return result


def request_details(source, parsed):
    sid=source['id']
    if not parsed:
        return '<p class="request-full prose" data-request="'+esc(sid)+'"></p>'
    result='<div class="command-details">'
    for key,label in (('arguments','Argument'),('command','Command'),('message','Message')):
        text=parsed[key]
        if text is None:continue
        element_id='request-'+sid+'-'+key
        result+='<div class="command-field"><div><p class="small muted">'+label+'</p><pre id="'+esc(element_id)+'">'+esc(text)+'</pre></div><button type="button" class="link command-copy" data-copy-field="'+esc(element_id)+'" aria-label="Copy '+label.lower()+' exactly">'+icon('copy')+'Copy '+label.lower()+'</button></div>'
    result+='<div class="command-source"><details><summary>Original masked record</summary><pre class="request-full" data-request="'+esc(sid)+'"></pre></details>'+source_button(sid,'Open in source')+'</div></div>'
    return result


TOKEN_FIELDS = (('prompt_tokens','Input total'),('uncached_input_tokens','Uncached input'),
                ('cache_creation_tokens','Cache write'),('cached_tokens','Cache read'),('completion_tokens','Output'))


def metric_cell(key, label, metric):
    metric=metric or {}
    value=metric.get('value')
    content='<div data-metric="'+key+'"><dt>'+esc(label)+'</dt><dd title="'+esc(metric.get('definition',''))+'"><strong>'+number(value)+'</strong></dd>'
    if value is None and metric.get('known_subtotal') is not None:
        content+=prose('Known subtotal '+number(metric['known_subtotal']),'small muted')
    if metric.get('known')!=metric.get('eligible'):
        content+=prose(str(metric.get('known',0))+'/'+str(metric.get('eligible','?'))+' recorded','small muted')
    if metric.get('inferred_origin_count'):
        content+=prose(str(metric['inferred_origin_count'])+' inferred origins','small muted')
    return content+'</div>'


def token_breakdown(metrics, label):
    return ('<div class="token-breakdown" aria-label="'+esc(label)+'"><p class="small muted token-note">Input total includes uncached input, cache write and cache read.</p>'
            +'<dl class="token-metrics">'+''.join(metric_cell(key,title,metrics.get(key)) for key,title in TOKEN_FIELDS)+'</dl></div>')


def metric_details(metrics):
    return detail('Definitions and measurement coverage',{k:{a:b for a,b in m.items() if a!='source_ids'} for k,m in metrics.items()})


def span_label(value):
    if value is None:return 'Unknown'
    seconds=round(value*60);hours,rest=divmod(seconds,3600);minutes,seconds=divmod(rest,60)
    return (str(hours)+'h ' if hours else '')+str(minutes)+'m '+str(seconds)+'s'


def verification_html(checks, prerequisites=None, context=None):
    content=''
    for index,check in enumerate(checks):
        content+='<div class="evidence-check">'+prose(check['description'])+prose(check['outcome'].replace('_',' ')+' · scope '+check['scope_relation']+' · revision '+check['revision_relation'].replace('_',' '),'small muted')
        check_context={**context,'label':check['description'],'text':check['basis']} if context else None
        content+=prose(check['basis'],'small')+refs_html(check['references'],check_context)
        flags=(prerequisites or [])[index].get('qualifications',[]) if index<len(prerequisites or []) else []
        if flags:content+=prose(' · '.join(f.replace('_',' ') for f in flags),'limit small')
        content+='</div>'
    return content


def review_qualification(data, record_id):
    """Show the actual current review next to its subject; never repair prose."""
    reviews=[r['check'] for r in data.get('review_checks',[]) if r['check']['record_id']==record_id]
    if not reviews or reviews[-1]['verdict']=='supported': return ''
    review=reviews[-1]
    body='<aside class="review-qualification"><p class="small"><strong>Claude review · '+esc(review['verdict'].replace('_',' '))+'</strong></p>'+prose(review['assessment'])
    for uncertainty in review['remaining_uncertainty']: body+=prose(uncertainty,'limit small')
    for check in review.get('semantic_checks',[]):
        if check['verdict']=='needs_revision': body+=prose(check['assessment'],'limit small')
    return body+'</aside>'


def requirements_html(data):
    saved=data.get('requirement_map')
    if not saved:return ''
    mapped=saved['requirement_map']; items=mapped['requirements']
    unverified=sum(i['status']=='unverified' for i in items)
    content=prose(mapped['scope'])+prose(mapped['inventory_status'].replace('_',' '),'small muted')+review_qualification(data,saved['id'])
    for limit in mapped['limitations']:content+=prose(limit,'limit small')
    content+='<div class="table-scroll"><table class="requirements-table"><thead><tr><th>Requested</th><th>Status</th><th>Result and verification</th></tr></thead><tbody>'
    for item in items:
        context=evidence_context(saved['id'],item['description'],item['status_basis'],item['missing_evidence'])
        anchor=requirement_anchor(saved['id'],item['key'])
        content+='<tr id="'+anchor+'" class="requirement-row"><th scope="row"><button class="link requirement-toggle" data-requirement="'+anchor+'" aria-expanded="false" aria-controls="detail-'+anchor+'">'+icon('chevron-right')+'<span>'+esc(item['description'])+'</span></button></th><td><span class="requirement-status '+esc(item['status'])+'">'+REQUIREMENT_STATUS[item['status']]+'</span></td><td>'
        # Literal saved basis; CSS shortens the preview, not the underlying text.
        content+='<p class="requirement-preview" title="'+esc(item['status_basis'])+'">'+esc(item['status_basis'])+'</p>'
        content+=reference_list(item['result_references']+[r for c in item['verification'] for r in c['references']],context)+'</td></tr>'
        content+='<tr id="detail-'+anchor+'" class="requirement-detail" hidden><td colspan="3"><article class="requirement"><h3>'+esc(item['description'])+'</h3>'+prose(REQUIREMENT_STATUS[item['status']],'meta')
        if item.get('delivered_response_evidence'):
            delivered=item['delivered_response_evidence']
            content+=prose('Requested response content','small muted')+prose(delivered['basis'])+refs_html(delivered['references'],{**context,'text':delivered['basis']})
        content+=prose(item['scope'],'small muted')+prose(item['status_basis'])
        content+='<p class="small">Intent '+refs_html(item['intent_references'],context)+'</p>'
        if item['result_references']:content+='<p class="small">Result '+refs_html(item['result_references'],context)+'</p>'
        revision=item['artifact_revision']
        content+=prose('Artifact revision: '+(revision.get('value') if revision['state']=='known' else revision['state'].replace('_',' ')),'small muted')+refs_html(revision['references'],context)
        content+=verification_html(item['verification'],saved['verification_prerequisites'].get(item['key']),context)
        for change in item['intent_changes']:content+=prose(change['description'],'small')+refs_html(change['references'],{**context,'text':change['description']})
        for gap in item['missing_evidence']:content+=prose(gap,'limit small')
        if item['merged_from']:content+=prose('Merged historical requirements: '+', '.join(item['merged_from']),'small muted')
        if item['superseded_by']:content+=prose('Superseded by: '+', '.join(item['superseded_by']),'small muted')
        turn_ids=related_turns(data,requirement_refs(item))
        if turn_ids:content+=focus_turns_button(turn_ids,'Related turns')
        content+='</article></td></tr>'
    content+='</tbody></table></div>'
    content+=detail('Inventory coverage and saved versions',{'coverage':saved['request_coverage'],'history':data.get('requirement_map_history',[])})
    return '<details id="requirements"><summary>Requirements · '+str(len(items))+' mapped'+(' · '+str(unverified)+' unverified' if unverified else '')+'</summary>'+content+'</details>'


def focus_turns_button(turn_ids, label='Related turns'):
    return '<button class="link" data-focus-turns="'+esc(canonical(turn_ids))+'">'+esc(label)+'</button>'


def remaining_work_html(data):
    items=remaining_items(data)
    if not items:return ''
    body='<section class="remaining-work" aria-labelledby="remaining-heading"><div class="section-heading"><h3 id="remaining-heading">Remaining work and evidence</h3><button class="link" data-copy-field="remaining-work-text">'+icon('copy')+'Copy remaining work</button></div><ul>'
    for item in items:
        body+='<li><span class="small muted">'+esc(item['status'])+'</span> '
        if item['kind']=='requirement':body+='<button class="link" data-open-requirement="'+esc(item['id'])+'">'+esc(item['title'])+'</button>'
        else:body+='<button class="link" data-finding="'+esc(item['id'])+'">'+esc(item['title'])+'</button>'
        review=item.get('review')
        if review and review['verdict']!='supported':body+='<span class="limit small"> · Claude review '+esc(review['verdict'].replace('_',' '))+'; see saved assessment</span>'
        if item.get('next_action'):body+=prose('Next action: '+item['next_action'],'small prose')
        if item['turn_ids']:body+=focus_turns_button(item['turn_ids'])
        body+='</li>'
    body+='</ul>'+detail('Handoff text', '<pre id="remaining-work-text">'+esc(remaining_work_text(data))+'</pre>',raw=True)+'</section>'
    return body


def context_html(data, agent_id='main', turn=None):
    view=data.get('resource_views',{}).get(agent_id,{}).get('context')
    if not view:return ''
    items=view['items']
    if turn:items=[i for i in items if set(i['source_ids']).intersection(turn['event_ids'])]
    content=prose(view['limitation'],'small muted')
    if not turn:
        peak=view['peak_input']; share=view['cache_read_share']
        content+=prose('Peak observed input: '+number(peak['known_maximum'])+' · '+str(peak['known'])+'/'+str(peak['eligible'])+' inputs recorded.','small')
        content+=prose('Cache-read share: '+(number(share['value']*100)+'%' if share['value'] is not None else 'Unknown')+' · matched known population '+str(share['known'])+'/'+str(share['eligible'])+'.','small')
    content+='<div class="resource-page"><div class="table-scroll" tabindex="0" aria-label="Context and cache timeline"><table class="resource-table"><thead><tr><th>Record</th><th>Input total</th><th>Uncached</th><th>Cache write</th><th>Cache read</th><th>Output</th><th>Read share</th></tr></thead><tbody>'
    for p in items:
        refs=[{'source_id':s} for s in p['source_ids']]
        if p['kind']=='response':
            t=p['tokens']; share=p['cache_read_share']['value']
            content+='<tr><td>'+source_button(p['source_ids'][0],p.get('timestamp') or 'Response')+'</td>'+''.join('<td>'+number(t.get(k))+'</td>' for k in ('total_input_tokens','input_tokens','cache_creation_input_tokens','cache_read_input_tokens','output_tokens'))+'<td>'+(number(share*100)+'%' if share is not None else 'Unknown')+'</td></tr>'
        else:
            content+='<tr class="timeline-boundary"><td colspan="7">'+esc(p['kind'].replace('_',' ').capitalize())+' '+refs_html(refs)
            if p['kind']=='model_change':content+=prose(', '.join(p['from'])+' → '+', '.join(p['to']),'small')
            if p['kind']=='recorded_compaction':
                pre,post=p['before'],p['after']
                content+=prose('Observed input before / after: '+number(pre['tokens']['total_input_tokens'] if pre else None)+' / '+number(post['tokens']['total_input_tokens'] if post else None)+' · cache-read change '+number(p['cache_read_percentage_point_change'])+' percentage points · recorded compaction duration '+number(p['recorded_duration_ms'])+' ms','small')
                content+=detail('Compaction metadata and response identities',p)
            content+='</td></tr>'
    if not items:content+='<tr><td colspan="7">No attributable response or compaction records in this selection.</td></tr>'
    content+='</tbody></table></div><button class="link" data-resource-more hidden>Show more records</button></div>'
    if not turn:content+=detail('Population, definitions and unknown inputs',{k:v for k,v in view.items() if k!='items'})
    return detail('Context and cache timeline',content,raw=True)


def output_html(data, agent_id='main', turn=None):
    view=data.get('resource_views',{}).get(agent_id,{}).get('outputs')
    if not view:return ''
    items=view['items']
    if turn:items=[i for i in items if i['tool_id'] in turn['tool_ids']]
    if not items:return ''
    content=prose(view['limitation'],'small muted')+'<div class="resource-page"><div class="table-scroll" tabindex="0" aria-label="Captured tool outputs"><table><thead><tr><th>Tool and source</th><th>Captured bytes</th><th>Same input / result · agent</th><th>Truncation marker</th></tr></thead><tbody>'
    for item in items:
        content+='<tr><td>'+esc(item['name'])+' '+refs_html([{'source_id':s} for s in item['source_ids']])+'</td><td>'+number(item['captured_result_bytes'])+'</td><td>'+str(item.get('same_input_count',len(item.get('same_input_tool_ids',[]))))+' / '+str(item.get('same_result_count',len(item.get('same_result_tool_ids',[]))))+'</td><td>'
        content+=('Candidate · '+refs_html([{'source_id':s} for s in item['truncation_marker_source_ids']])) if item['truncation_marker_source_ids'] else ('Not inspected' if item['truncation_detection']=='not_run' else 'Not found')
        content+='</td></tr>'
    groups={field:{key:value for key,value in view.get(field,{}).items() if key in {i.get('input_group_id' if field=='input_groups' else 'result_group_id') for i in items}}
            for field in ('input_groups','result_groups')}
    content+='</tbody></table></div><button class="link" data-resource-more hidden>Show more records</button></div>'+detail('Exact retrieval identities and measurement definitions',{'items':items,**groups,'captured_bytes':view['captured_bytes'] if not turn else 'See selection identities; whole-agent totals are not assigned to this turn.'})
    return detail('Captured tool outputs',content,raw=True)


def analyzer_metrics(run):
    """Display host usage separately; never sum nested iteration/provider copies."""
    usage=run.get('analyzer_usage') or {}
    rows=usage.get('usage')
    if isinstance(rows,dict):rows=[{'phase':'Analysis','usage':rows}]
    content=''
    for row in rows or []:
        values=row.get('usage') or {}
        keys=('input_tokens','cache_creation_input_tokens','cache_read_input_tokens')
        total=sum(values[k] for k in keys) if all(isinstance(values.get(k),(int,float)) for k in keys) else None
        metrics={key:{'value':values.get(host)} for key,host in (('uncached_input_tokens','input_tokens'),('cache_creation_tokens','cache_creation_input_tokens'),('cached_tokens','cache_read_input_tokens'),('completion_tokens','output_tokens'))}
        metrics['prompt_tokens']={'value':total}
        content+='<h4>'+esc(row.get('phase','Analysis').replace('_',' ').capitalize())+'</h4>'+token_breakdown(metrics,'Analyzer '+row.get('phase','Analysis')+' tokens')
    if not content:content+=prose('Analyzer token usage was not recorded.','small muted')
    if usage.get('elapsed_seconds') is not None:content+=prose('Analyzer elapsed span: '+number(usage['elapsed_seconds'])+' s','small muted')
    if usage.get('cost_usd') is not None:content+=prose('Host-reported cost: $'+str(usage['cost_usd']),'small muted')
    content+=detail('Exact host usage and provenance',usage)
    return detail('Analyzer usage · separate from the source session',content,raw=True)


def detail(title, content, raw=False):
    return '<details><summary>'+esc(title)+'</summary>'+(content if raw else '<pre>'+esc(json.dumps(content,ensure_ascii=False,indent=2,sort_keys=True))+'</pre>')+'</details>'


def source_button(ref, label='Source', cls='link', context=None):
    if isinstance(ref,str): ref={'source_id':ref}
    return '<button type="button" class="'+cls+' source-link" data-ref="'+esc(canonical(ref))+'"'+(' data-source-context="'+esc(canonical(context))+'"' if context else '')+'>'+icon('link-2')+esc(label)+'</button>'


def refs_html(refs, context=None):
    return ' '.join(source_button(r, r.get('explanation') or 'Source '+str(i), context=context) for i,r in enumerate(refs,1))


def reference_list(refs, context=None):
    if not refs:return ''
    return '<details class="source-list"><summary>'+icon('link-2')+'Sources · '+str(len(refs))+'</summary><div>'+refs_html(refs,context)+'</div></details>'


def evidence_context(owner, label, text, limitations=()):
    """Navigation context only. All substantive text comes from the saved record."""
    return {'owner_id':owner,'label':label,'text':text,'limitations':list(limitations)}


def item_refs(incident):
    return (incident['task_references'] + incident['recovery_references'] + incident['counterevidence']
            + [r for c in incident['claims'] for r in c['references']])


def turn_incidents(data):
    result = defaultdict(list)
    for saved in data['incidents']:
        incident = saved['incident']
        sources = set(incident['member_event_ids']) | {r['source_id'] for r in item_refs(incident)}
        for turn in data['accounting']['turns']:
            if sources.intersection(turn['event_ids']) or set(incident['tool_ids']).intersection(turn['tool_ids']):
                result[turn['id']].append(saved)
    return result


def pattern_failure_entries(data, pattern):
    """Resolve the exact requested invocations counted by a pattern's failure metric."""
    tool_map = {t['id']:t for t in data.get('tools',[])}
    entries = []
    if 'member_tool_ids' in pattern:
        owners={tid:(index,turn) for index,turn in enumerate(data['accounting']['turns'],1) for tid in turn['tool_ids']}
        for tid in pattern['member_tool_ids']:
            tool=tool_map.get(tid)
            if tool and tool['requested'] and tool['outcome'] in RECORDED_FAILURE_OUTCOMES:
                index,turn=owners.get(tid,(None,None))
                entries.append((index,turn,tool))
        return sorted(entries,key=lambda x:(x[2].get('timestamp') or '',x[2]['id']))
    for index, turn in enumerate(data['accounting']['turns'],1):
        if turn['id'] not in pattern['member_turn_ids']:
            continue
        selected = [tool_map[tid] for tid in turn['tool_ids'] if tid in tool_map]
        for tool in sorted(selected,key=lambda t:(t.get('timestamp') or '',t['id'])):
            if tool['requested'] and tool['outcome'] in RECORDED_FAILURE_OUTCOMES:
                entries.append((index,turn,tool))
    return entries


def failure_dialog(data, pattern):
    sources = data.get('sources',{})
    entries = pattern_failure_entries(data,pattern)
    explanations = active_explanations(data.get('failure_explanations',[]))
    pid = esc(pattern['id'])
    body = '<dialog class="failure-dialog" id="failures-'+pid+'" aria-labelledby="failures-title-'+pid+'"><div class="dialog-head"><h2 id="failures-title-'+pid+'">Recorded failures · '+esc(pattern['archetype'])+'</h2><button data-close aria-label="Close failures">Close</button></div>'
    body += prose(str(pattern['recorded_failures'])+' recorded tool '+('failure' if pattern['recorded_failures']==1 else 'failures')+'. A failure may be expected or later recovered.','small muted')
    if len(entries)!=pattern['recorded_failures']:
        body += prose('Invocation details are available for '+str(len(entries))+' of the '+str(pattern['recorded_failures'])+' failures in the saved count.','limit small')
    for index,turn,tool in entries:
        turn_link=' · <a data-turn-link="'+esc(turn['id'])+'" href="#'+esc(turn['id'])+'">Turn '+str(index)+'</a>' if turn else ''
        body += '<article class="failure-entry" data-failure-tool="'+esc(tool['id'])+'"><h3>'+esc(tool['name'])+turn_link+'</h3>'
        meta = [tool['outcome'].replace('_',' ')]
        if tool.get('exit_code') is not None: meta.append('Exit code '+str(tool['exit_code']))
        if tool.get('result_timestamp') or tool.get('timestamp'): meta.append(tool.get('result_timestamp') or tool['timestamp'])
        saved = explanations.get(tool['id'])
        if saved:
            e = saved['explanation']
            if e['status']=='insufficient_evidence': body += prose('Insufficient evidence','limit small')
            body += prose(e['summary'],'failure-summary prose')
            body += prose(e['follow_up'],'prose')
            if e['limitations']: body += ''.join(prose(limit,'limit small prose') for limit in e['limitations'])
            labels = {'recovered':'Recovered', 'unresolved':'Unresolved', 'unknown':'Recovery unknown', 'not_applicable':'Recovery not applicable'}
            body += prose(labels[e['resolution']],'small muted')
            body += review_qualification(data,saved['id'])
            body += '<div class="failure-evidence">'
            for i,ref in enumerate(e['references'],1):
                role = sources.get(ref['source_id'],{}).get('role')
                label = {'tool_call':'Input', 'tool_result':'Result', 'user_statement':'Request'}.get(role,'Context')
                body += source_button(ref,label+' '+str(i),context=evidence_context(saved['id'],'Failure explanation',e['summary'],e['limitations']))
            for i,ref in enumerate(e['recovery_references'],1):
                body += source_button(ref,'Follow-up '+str(i),context=evidence_context(saved['id'],'Recovery',e['follow_up'],e['limitations']))
            body += '</div>'
        else:
            body += prose('No explanation was saved for this attempt.','limit prose')
        raw = prose(' · '.join(meta),'small muted')
        results = [sources[sid] for sid in tool['evidence'] if sources.get(sid,{}).get('role')=='tool_result']
        for result in results:
            if 'text' in result:
                text = result['text']
                raw += '<pre class="failure-preview">'+esc(text[:600]+('…' if len(text)>600 else ''))+'</pre>'
        if not any('text' in s for s in results):
            raw += prose('Result text is not included in this report.','small muted')
        raw += '<div class="failure-evidence">'
        for sid in tool['evidence']:
            label = {'tool_result':'Full result','tool_call':'Tool input'}.get(sources.get(sid,{}).get('role'),'Source record')
            raw += source_button(sid,label,context=evidence_context(saved['id'],'Failure explanation',e['summary'],e['limitations']) if saved else None)
        raw += '</div>'+detail('Invocation identity and classification',{'tool_id':tool['id'],'outcome':tool['outcome'],
                              'outcome_basis':tool.get('outcome_basis'),'evidence':tool['evidence']})
        body += detail('Original tool input and result',raw,raw=True)
        if saved: body += detail('Saved explanation and evidence checks',saved)
        body += '</article>'
    parents=[d for d in data.get('delegations',[]) if d['tool_id'] in pattern.get('return_invocation_ids',[])]
    if parents:body+='<p>'+', '.join(subagent_button(d,'Back to subagent' if len(parents)==1 else 'Invocation '+d['tool_id']) for d in parents)+'</p>'
    return body+'</dialog>'


def subagent_button(invocation, label=None):
    return '<button type="button" class="link" data-subagent="'+esc(invocation['tool_id'])+'" aria-haspopup="dialog">'+esc(label or (invocation['name']+' invocation'))+'</button>'


def agent_failure_group(agent):
    return {'id':'agent-'+digest(agent['agent_id'])[:16], 'archetype':'Subagent '+agent['agent_id'],
            'member_tool_ids':agent['failure_tool_ids'],'recorded_failures':len(agent['failure_tool_ids']),
            'return_invocation_ids':agent['parent_invocation_ids']}


def subagent_dialog(data, invocation):
    tid=invocation['tool_id']; agents=data['agents']; sources=data['sources']
    body='<dialog class="subagent-dialog" id="subagent-'+esc(tid)+'" aria-labelledby="subagent-title-'+esc(tid)+'"><div class="dialog-head"><h2 id="subagent-title-'+esc(tid)+'">Subagent invocation</h2><button data-close aria-label="Close subagent">Close</button></div>'
    body+=prose(invocation['name']+' · '+invocation['outcome'].replace('_',' '),'meta')
    if invocation.get('label'):body+=prose(invocation['label'],'prose')
    if invocation.get('task_text'):
        task=invocation['task_text'];body+=detail('Assigned task',prose(task[:1200]+('…' if len(task)>1200 else ''),'prose small')+source_button(invocation['invocation_source_id'],'Full task and invocation'),raw=True)
    if invocation['outcome']=='launched':body+=prose('Launch acknowledged; completion is not established by that result.','limit small')
    body+='<div class="failure-evidence">'+''.join(source_button(sid,{'tool_call':'Invocation input','tool_result':'Returned result'}.get(sources.get(sid,{}).get('role'),'Source')) for sid in invocation['evidence_ids'])+'</div>'
    if invocation['reported_child_summary']:
        body+=detail('Parent-reported child totals · not added to observed usage',invocation['reported_child_summary'])
    if not invocation['child_agent_ids']:
        body+=prose('No structured child identity was captured for this invocation. A child trace cannot be matched reliably.','limit prose')
    for aid in invocation['child_agent_ids']:
        a=agents[aid]
        body+='<section class="subagent-section"><h3>'+esc(aid)+((' · '+esc(a['role'])) if a['role']!='unknown' else '')+'</h3>'
        if a['trace_status']=='unavailable':
            body+=prose('Child trace unavailable. The parent invocation and returned result are retained; the child’s own actions, usage and outcome cannot be verified.','limit prose')+'</section>'
            continue
        m=a['metrics']
        body+=token_breakdown(m,'Child-agent tokens')+'<dl class="turn-metrics">'
        for key,label in (('llm_calls','LLM calls · observed'),('tool_invocations','Tool invocations'),('session_duration_minutes','Observed span (min)')):
            body+=metric_cell(key,label,m[key])
        body+='</dl>'+metric_details(m)+context_html(data,aid)+output_html(data,aid)
        if a['shared_response_ids'] or a['shared_tool_ids']:body+=prose('Shared response or tool identities are excluded from this agent’s counts; combined accounting retains them once.','limit small')
        if len(a['parent_invocation_ids'])>1:body+=prose('This trace is shared by '+str(len(a['parent_invocation_ids']))+' invocations. Its records and metrics are not partitioned per invocation.','limit small')
        body+=prose('Captured trace · completeness not established. Observed spans include idle intervals.','small muted')
        if a['failure_tool_ids']:
            group=agent_failure_group(a)
            body+='<p><button class="link" data-failures="'+esc(group['id'])+'">Recorded failures · '+str(len(a['failure_tool_ids']))+'</button></p>'
        last=sources.get(a['last_message_source_id'],{})
        if last:
            body+='<h4>Last captured assistant message</h4>'
            if 'text' in last:body+=prose(last['text'][:1200]+('…' if len(last['text'])>1200 else ''),'prose small')
            body+=source_button(a['last_message_source_id'],'Full message and source')
        nested=[d for d in data['delegations'] if d['tool_id'] in a['invocation_ids']]
        if nested:body+='<h4>Nested invocations</h4><div class="failure-evidence">'+''.join(subagent_button(d,d['name']+' · '+(', '.join(d['child_agent_ids']) or 'identity unavailable')) for d in nested)+'</div>'
        body+='<h4>Child source records</h4><div data-agent-events="'+esc(aid)+'"></div><button class="link" data-agent-more="'+esc(aid)+'">Show next child records</button></section>'
    parent_calls={pid for aid in invocation['parent_agent_ids'] if aid!='main' for pid in agents.get(aid,{}).get('parent_invocation_ids',[])}
    for parent in data['delegations']:
        if parent['tool_id'] in parent_calls:body+='<p>'+subagent_button(parent,'Parent invocation')+'</p>'
    return body+detail('Invocation identity and linkage',invocation)+'</dialog>'


def render_report(data, embedded=False):
    display_accounting=data.get('main_accounting',data['accounting'])
    run, session = data['investigation'], display_accounting['session']
    conclusion_owner=run.get('review_workflow',{}).get('latest_draft_id')
    draft=next((d for d in data.get('conclusion_drafts',[]) if d['id']==conclusion_owner),None)
    if not draft or any(draft['conclusion'].get(k)!=run.get(k) for k in ('synopsis','observed_outcome','summary')):
        conclusion_owner=None
    sources, turns = data.get('sources',{}), display_accounting['turns']
    mapping = turn_incidents(data)
    title = run.get('title') or 'Session '+run['root_session_id'][:12]
    dates = sorted(s['timestamp'] for s in sources.values() if s.get('timestamp'))
    try: date = datetime.fromisoformat(dates[0].replace('Z','+00:00')).strftime('%b %d, %Y')+' · UTC'
    except (ValueError,IndexError): date = 'Session date unavailable'
    status = {'running':'Investigation not finished','created':'Investigation not run','completed':'Investigation completed',
              'partial':'Incomplete investigation','failed':'Investigation failed'}.get(run['run_status'],run['run_status'])
    if run['run_status']=='running' and not data['incidents'] and not data.get('inquiries') and not data['exposure'].get('requests'):
        status = 'Investigation not run'
    body = '<div class="product"><div><b>Ally</b><span> / Session report</span></div><div class="product-actions"><button class="link source-reopen" data-source-reopen aria-controls="source-dialog" aria-expanded="false" aria-label="Reopen selected source" hidden>'+icon('chevron-left')+'Source</button><span class="product-date">'+esc(date)+'</span><details class="export"><summary>'+icon('download')+'Export</summary><div><button data-export="html">HTML report</button><button data-export="json">JSON report</button></div></details></div></div>'
    body += '<nav class="report-nav" aria-label="Report sections">'+''.join('<a href="#'+key+'"'+(' aria-current="location"' if key=='overview' else '')+'>'+label+'</a>' for key,label in (('overview','Overview'),('outcome','Outcome'),('turns-heading','Turns'),('findings-heading','Findings'),('proposals-heading','Proposed changes'),('coverage','Coverage')))+'</nav><main id="report-column"><header id="overview"><h1>'+esc(title)+'</h1><p class="meta">'+esc(date)+' · <span class="status-tag '+esc(run['run_status'])+'">'+esc(status)+'</span></p>'
    if run.get('synopsis'):
        synopsis = run['synopsis']
        body += prose(synopsis['text'],'synopsis prose')
        body += '<div class="evidence-line">'+reference_list(synopsis['references'],evidence_context(conclusion_owner,'Session synopsis',synopsis['text'],synopsis['limitations']))+'</div>'
        if synopsis['limitations']: body += '<details class="evidence-limits"><summary>Synopsis limits</summary>'+''.join(prose(x,'limit prose') for x in synopsis['limitations'])+'</details>'
    elif run.get('summary'):
        body += prose(run['summary'],'synopsis prose')+prose('Saved conclusion; this run did not record a separate session synopsis.','small muted')
    else: body += prose('No session synopsis has been saved.','muted')
    for check in data.get('report_checks',[]):
        if check['status']!='passed':
            body += prose('Coverage count needs review: “'+check['quoted_text']+'”; the captured scope records '+str(check['scope_value'])+' distinct missing child traces. Saved wording is unchanged.','limit small')
    body+='</header><section id="outcome">'
    outcome = run.get('observed_outcome')
    if outcome:
        body += '<h2>Outcome</h2>'+prose(outcome['text'],'outcome prose')
        body += '<div class="evidence-line"><span>'+esc(outcome['evidence_class'].replace('_',' ').capitalize())+'</span>'+reference_list(outcome['references'],evidence_context(conclusion_owner,'Outcome',outcome['text'],outcome['limitations']))+'</div>'
        if outcome['limitations']: body += '<details class="evidence-limits"><summary>Evidence limits</summary>'+''.join(prose(x,'limit prose') for x in outcome['limitations'])+'</details>'
        if conclusion_owner:body+=review_qualification(data,conclusion_owner)
    gaps = data['scope']['capture_gaps']; material = []
    main_agent=data.get('agents',{}).get('main',{})
    if main_agent.get('shared_response_ids'):material.append(str(len(main_agent['shared_response_ids']))+' shared response identities excluded from main-agent counts')
    if main_agent.get('shared_tool_ids'):material.append(str(len(main_agent['shared_tool_ids']))+' shared tool identities excluded from main-agent counts')
    if gaps['missing_child_traces']: material.append(str(len({x['child_agent_id'] for x in gaps['missing_child_traces']}))+' child traces unavailable')
    if gaps.get('unlinked_agent_count'): material.append(str(gaps['unlinked_agent_count'])+' unlinked agents excluded')
    coverage = data['accounting']['attribution_coverage']
    unassigned = len(coverage.get('responses_without_unambiguous_turn',[]))
    if unassigned: material.append(str(unassigned)+' responses not assigned to a turn')
    if not data.get('source_text_included'): material.append('Source text not included in this export')
    if material: body += prose(' · '.join(material),'coverage-note')
    if run['run_status'] in ('partial','failed'):
        body += prose(run.get('stop_reason','No stop reason saved.'),'limit prose')
    body += remaining_work_html(data)
    body += requirements_html(data)
    body += '</section><section class="metrics" aria-label="Main session metrics"><div class="metric-counts">'
    request_key='task_requests' if 'task_requests' in session else 'user_turns'
    for key,label in ((request_key,'task requests' if request_key=='task_requests' else 'turns'),('llm_calls','observed calls'),('tool_invocations','tools')):
        m=session[key]
        body+='<span title="'+esc(m['definition'])+'"><strong>'+number(m['value'])+'</strong> '+label+'</span>'
    body+='</div><details id="metrics"><summary><span>Metrics</span><span class="metric-preview">'+compact(session['prompt_tokens']['value'])+' input tokens · '+compact(session['completion_tokens']['value'])+' output tokens · '+span_label(session['session_duration_minutes']['value'])+' observed span</span></summary>'
    body+=token_breakdown(session,'Main-agent tokens')+'<dl class="turn-metrics">'+''.join(metric_cell(k,l,session[k]) for k,l in (('user_turns','User turns'),('llm_calls','LLM calls · observed'),('tool_invocations','Tool invocations'),('session_duration_minutes','Observed span (min)')))+'</dl>'
    if 'task_requests' in session:
        body+='<dl class="turn-metrics">'+metric_cell('task_requests','Task requests',session['task_requests'])+metric_cell('human_origin_turns','Recorded human-origin turns',session['human_origin_turns'])+'</dl>'
        body+=prose('SDK submissions are task requests, not human-origin turns. Unspecified origins remain inferred.','small muted')
    body+=prose('Observed spans include idle intervals. Recorded turn durations are shown separately in each turn.','small muted')+metric_details(session)+context_html(data)+'</details>'
    body+=prose('Main-agent metrics. Combined main and captured child totals are in Coverage.' if data.get('delegations') else 'Main-agent metrics.','small muted')+'</section>'
    body += '<section aria-labelledby="turns-heading"><div class="section-heading"><h2 id="turns-heading">Turns</h2>'
    body+='<span class="small muted" id="turn-selection-status" role="status">'+str(len(turns))+' turns · complete chronology</span>'
    body+='</div><div class="turn-filters"><button class="link" data-all-turns aria-pressed="true">All turns</button>'
    pending=list(dict.fromkeys(t for item in remaining_items(data) for t in item['turn_ids']))
    episodes=[i['incident']['episode'] for i in data['incidents'] if i['incident'].get('episode')]
    episode_turns=related_turns(data,event_ids=[s for e in episodes for a in e['attempts'] for s in a['event_ids']],tool_ids=[t for e in episodes for a in e['attempts'] for t in a['tool_ids']])
    if pending:body+=focus_turns_button(pending,'Open work and evidence')
    if episode_turns:body+=focus_turns_button(episode_turns,'Recovery episodes')
    body+='</div><p class="table-hint">Scroll the table horizontally for findings.</p><div class="table-scroll" tabindex="0" aria-label="Turn table"><table class="turns"><thead><tr><th aria-label="Expand"></th><th>#</th><th>Request</th><th>LLM calls</th><th>Tools</th><th>Findings</th></tr></thead><tbody>'
    for index,turn in enumerate(turns,1):
        sid = turn['request_event_id']; source=sources.get(sid,{})
        parsed = command_request(source)
        preview = request_preview(source, parsed)
        links = ''.join('<button class="link finding-link" data-finding="'+esc(i['id'])+'" title="'+esc(i['incident']['title'])+'">'+esc(i['incident']['title'])+'</button>' for i in mapping[turn['id']]) or '—'
        body += '<tr id="'+esc(turn['id'])+'" class="turn-row"><td><button class="turn-toggle" data-turn="'+esc(turn['id'])+'" aria-expanded="false" aria-controls="detail-'+esc(turn['id'])+'" aria-label="Expand turn '+str(index)+'">'+icon('chevron-right')+'</button></td><th scope="row">'+str(index)+'</th><td class="request"><button class="request-control'+(' command-preview' if parsed else '')+'" data-turn="'+esc(turn['id'])+'" aria-expanded="false" aria-controls="detail-'+esc(turn['id'])+'" aria-label="Read turn '+str(index)+'">'+preview+'</button></td><td>'+number(turn['metrics']['llm_calls']['value'])+'</td><td>'+number(turn['metrics']['tool_invocations']['value'])+'</td><td>'+links+'</td></tr>'
        body += '<tr id="detail-'+esc(turn['id'])+'" class="turn-detail" hidden><td colspan="6"><div class="turn-content"><div class="turn-detail-head"><h3>Turn '+str(index)+'</h3>'+(source_button(sid,'Full request and source') if not parsed else '')+'</div>'+request_details({**source,'id':sid},parsed)+token_breakdown(turn['metrics'],'Turn '+str(index)+' tokens')+'<dl class="turn-metrics">'
        for key,label in (('turn_duration_seconds','Recorded duration (s)'),('observed_turn_span_seconds','Observed span (s)')):
            body += metric_cell(key,label,turn['metrics'][key])
        body += '</dl><p class="small muted">'+esc(turn['origin_basis'].replace('_',' '))+' · Observed spans include idle intervals.</p>'+metric_details(turn['metrics'])+context_html(data,'main',turn)+output_html(data,'main',turn)
        delegated=[d for d in data.get('delegations',[]) if d['tool_id'] in turn['tool_ids']]
        if delegated:
            body+='<h4>Subagent invocations</h4><div class="delegation-list">'
            for d in delegated:
                captured=sum(data['agents'][aid]['trace_status']=='captured' for aid in d['child_agent_ids'])
                state=(str(captured)+' captured · '+str(len(d['child_agent_ids'])-captured)+' unavailable') if d['child_agent_ids'] else 'Child identity unavailable'
                label=d.get('label') or ', '.join(d['child_agent_ids']) or 'unlinked'
                body+='<p>'+subagent_button(d,d['name']+' · '+label[:100]+('…' if len(label)>100 else ''))+' <span class="small muted">'+esc(state)+'</span></p>'
            body+='</div>'
        body+='<h4>Main source records</h4><div data-events="'+esc(turn['id'])+'"></div><button class="link" data-more="'+esc(turn['id'])+'">Show next records</button></div></td></tr>'
    if not turns: body += '<tr><td colspan="6">No task requests were identified by this report’s accounting policy. Request coverage is not established.</td></tr>'
    body += '</tbody></table></div>'
    assigned_tools={tid for t in turns for tid in t['tool_ids']}
    unassigned_invocations=[d for d in data.get('delegations',[]) if 'main' in d['parent_agent_ids'] and d['tool_id'] not in assigned_tools]
    if unassigned_invocations:body+='<p>Invocations without an attributed turn: '+', '.join(subagent_button(d,d.get('label') or d['tool_id']) for d in unassigned_invocations)+'</p>'
    linked = {s['id'] for values in mapping.values() for s in values}
    orphans = [s for s in data['incidents'] if s['id'] not in linked]
    if orphans:
        body += '<p>Findings outside an attributed turn: '+''.join('<button class="link finding-link" data-finding="'+esc(i['id'])+'">'+esc(i['incident']['title'])+'</button>' for i in orphans)+'</p>'
    body += '</section><section aria-labelledby="findings-heading" class="findings-section"><h2 id="findings-heading">Findings</h2>'
    for saved in data['incidents']:
        body += '<article class="finding-index"><h3><button class="link" data-finding="'+esc(saved['id'])+'">'+esc(saved['incident']['title'])+'</button></h3></article>'
    if not data['incidents']:
        body += prose('No findings saved.','muted')
    body += '</section><section aria-labelledby="proposals-heading" class="proposals-section"><h2 id="proposals-heading">Proposed changes</h2>'
    for saved in data['recommendations']:
        p = saved['recommendation']; validation = data['validation'][saved['id']]; edit = p.get('edit')
        target = {'use_existing_skill':'Existing skill','existing_skill':'Skill edit','new_skill':'New skill','claude_md':'CLAUDE.md'}.get(p['target_kind'],p['target_kind'].replace('_',' ').capitalize())
        body += '<article class="proposal" id="'+esc(saved['id'])+'"><div class="proposal-main"><p class="target">'+esc(target)+((' · '+esc(edit['target_path'])) if edit else '')+'</p><h3>'+esc(p['title'])+'</h3>'
        if edit:
            body += prose(edit['scope'],'small prose')+prose(edit['location'],'small muted prose')
            growth = data.get('edit_inspection',{}).get(saved['id'],{}).get('net_growth')
            if growth:
                growth_text = 'No file change' if edit['operation']=='invoke' else 'Net '+f"{growth['lines']:+,}"+' lines · '+f"{growth['words']:+,}"+' words · '+f"{growth['bytes']:+,}"+' bytes'
                body += '<p class="small muted" title="'+esc(growth['basis'])+'">'+growth_text+'</p>'
        body += '</div><div class="proposal-edit">'
        if edit:
            op = edit['operation']
            if op == 'invoke': body += '<pre class="invocation">'+esc(edit['invocation'])+'</pre>'
            else:
                if op in ('replace','insert_before','insert_after'):
                    body += '<pre class="diff '+('removed' if op=='replace' else 'anchor')+'"><span class="diff-marker" aria-hidden="true">'+('−' if op=='replace' else '↳')+'</span><code>'+esc(edit['original_text'])+'</code></pre>'
                body += '<pre class="diff added"><span class="diff-marker" aria-hidden="true">+</span><code>'+esc(edit['replacement_text'])+'</code></pre>'
        else: body += prose(p['change'])
        body += '<p class="readiness">'+esc(validation['status'].replace('_',' ').capitalize())+(' · Superseded' if validation['superseded_by'] else '')+'</p>'
        failures = [c for c in validation['checks'] if c['status']!='passed']
        if failures:
            body += '<ul class="small limit check-limits">'+''.join('<li>'+esc(c['check_type'].replace('_',' ').capitalize()+': '+c['status'].replace('_',' '))+'</li>' for c in failures)+'</ul>'
        else: body += prose('These checks do not establish benefit in subsequent sessions.','small muted')
        body += '</div><div class="proposal-actions">'
        if edit:
            label = 'Copy invocation' if edit['operation']=='invoke' else 'Copy new file' if edit['operation']=='create' else 'Copy insertion' if edit['operation'].startswith('insert') else 'Copy replacement'
            body += '<button class="outline" data-copy="'+esc(saved['id'])+'">'+icon('copy')+label+'</button>'
            if p.get('target_snapshot_id'): body += source_button(p['target_snapshot_id'],'View skill' if 'skill' in p['target_kind'] else 'View current target')
        for iid in p['incident_ids']:
            affected = [str(i) for i,t in enumerate(turns,1) if any(v['id']==iid for v in mapping[t['id']])]
            body += '<button class="link" data-finding="'+esc(iid)+'">Evidence'+(' · turns '+', '.join(affected) if affected else '')+'</button>'
        body += '</div><div class="proposal-detail">'
        plan = p['verification_plan']
        contents = prose(p['justification'])
        if edit: contents += prose(p['change'])
        contents += '<dl class="review">'+''.join('<dt>'+esc(k.replace('_',' ').capitalize())+'</dt><dd>'+esc(v if isinstance(v,str) else '; '.join(v))+'</dd>' for k,v in plan.items())+'</dl>'
        if p['tradeoffs']: contents += prose(' '.join(p['tradeoffs']))
        contents += refs_html(p['target_references'],evidence_context(saved['id'],'Proposed change',p['justification'],p['tradeoffs']))+detail('Exact saved proposal',saved)
        body += detail('Rationale and verification',contents,raw=True)+detail('Validation record',validation)+'</div></article>'
    if not data['recommendations']:
        if run['run_status'] in ('partial','failed'): empty = 'No recommendations saved. The investigation is incomplete.'
        elif run.get('conclusion')=='no_action_supported': empty = 'No justified change was identified in the investigated evidence.'
        elif run.get('conclusion')=='insufficient_evidence': empty = 'Insufficient evidence to justify a change.'
        elif run['run_status'] in ('running','created'): empty = 'No recommendations saved; the investigation has not reached a conclusion.'
        elif data.get('incidents'): empty = 'Findings were saved without a proposed change.'
        else: empty = 'No recommendations saved.'
        body += prose(empty)
    body += '</section><section class="appendices">'
    patterns = data.get('main_turn_patterns',data['turn_patterns'])
    pattern_html = '<p class="small">'+str(patterns['denominator'])+' reconstructed turns · shares count turns, not time or efficiency.</p><div class="table-scroll"><table><thead><tr><th>Pattern</th><th>LLM calls<br>median</th><th>Description</th><th>Share</th><th>Turns</th><th>Recorded failures</th></tr></thead><tbody>'
    for row in patterns['rows']:
        membership = ', '.join('<a data-turn-link="'+esc(t['id'])+'" href="#'+esc(t['id'])+'">'+str(i)+'</a>' for i,t in enumerate(turns,1) if t['id'] in row['member_turn_ids'])
        failure_count = number(row['recorded_failures'])
        if row['recorded_failures'] > 0:
            failure_count = '<button type="button" class="link failure-count" data-failures="'+esc(row['id'])+'" aria-haspopup="dialog" aria-controls="failures-'+esc(row['id'])+'" aria-label="Show '+str(row['recorded_failures'])+' recorded '+('failure' if row['recorded_failures']==1 else 'failures')+' in '+esc(row['archetype'])+'">'+failure_count+'</button>'
        pattern_html += '<tr><th scope="row">'+esc(row['archetype'])+'</th><td>'+number(row['median_llm_calls'])+'</td><td>'+esc(row['description'])+'</td><td>'+f"{row['share']*100:.1f}%"+'</td><td>'+membership+'</td><td>'+failure_count+(' · '+str(row['unknown_tool_outcomes'])+' unknown outcomes' if row['unknown_tool_outcomes'] else '')+'</td></tr>'
    pattern_html += '</tbody></table></div>'+detail('Classification and denominator',patterns)
    body += detail('Turn patterns',pattern_html,raw=True)
    cover = prose(run.get('coverage_explanation','No investigation coverage explanation saved.'))
    if run.get('unresolved_questions'): cover += '<ul>'+''.join('<li>'+esc(q)+'</li>' for q in run['unresolved_questions'])+'</ul>'
    if run.get('runner_unresolved_question'): cover += prose(run['runner_unresolved_question'])
    cover += detail('Investigation conclusion', {k:run.get(k) for k in ('summary','conclusion','stop_basis','stop_reason','diagnostic_review')})
    cover += detail('Investigation questions',data.get('inquiries',[]))
    if data.get('conclusion_drafts') or data.get('review_checks'):
        cover += detail('Claude drafts and evidence review',{'drafts':data.get('conclusion_drafts',[]),
                        'checks':data.get('review_checks',[]),'incident_history':data.get('incident_history',[])})
    cover += detail('Failure explanation coverage and history',{'coverage':data.get('failure_explanation_coverage'),
                                                              'records':data.get('failure_explanations',[])})
    cover += detail('Report checks',data.get('report_checks',[]))
    cover += detail('Main-agent metrics and coverage',token_breakdown(session,'Main-agent tokens in coverage')+metric_details(session),raw=True)
    if data.get('delegations'):
        combined=data['accounting']['session']
        cover+=detail('Combined main and captured child metrics',token_breakdown(combined,'Combined main and captured child tokens')+prose('Unavailable child traces are excluded; these are captured totals. Shared response identities are counted once.','small muted')+metric_details(combined),raw=True)
        for aid,agent in data.get('agents',{}).items():
            if aid=='main':continue
            if agent.get('metrics'):
                contents=token_breakdown(agent['metrics'],'Child '+aid+' tokens')+metric_details(agent['metrics'])
            else:contents=prose('Child trace unavailable. Usage is unknown.','limit small')
            cover+=detail('Child usage · '+aid,contents,raw=True)
        cover+=detail('Subagent linkage',data['delegations'])
    cover+=analyzer_metrics(run)
    cover+=output_html(data)
    cover += detail('Turn attribution',coverage)+detail('Capture gaps',gaps)+detail('Claude evidence access',data['exposure'])
    cover += detail('Measurements',data['measurements'])+detail('Run and source provenance',{'run':run,'scope':{k:v for k,v in data['scope'].items() if k!='event_ids'},'artifacts':data['artifacts']})
    cover += prose(data['rendering_contract'],'small muted')
    body += '<details id="coverage"><summary>Coverage</summary>'+cover+'</details></section></main>'
    for row in patterns['rows']:
        if row['recorded_failures'] > 0: body += failure_dialog(data,row)
    for invocation in data.get('delegations',[]):body+=subagent_dialog(data,invocation)
    for aid,agent in data.get('agents',{}).items():
        if aid!='main' and agent['failure_tool_ids']:body+=failure_dialog(data,agent_failure_group(agent))
    # Every finding is kept once in a modal; no duplicate recommendations in turns.
    for saved in data['incidents']:
        i = saved['incident']
        body += '<dialog class="finding-dialog" id="finding-'+esc(saved['id'])+'" aria-labelledby="title-'+esc(saved['id'])+'"><div class="dialog-head"><h2 id="title-'+esc(saved['id'])+'">'+esc(i['title'])+'</h2><button data-close aria-label="Close finding">Close</button></div>'
        body += prose(' · '.join(i[k].replace('_',' ') for k in ('expectedness','resolution','diagnosis')),'meta')
        body += review_qualification(data,saved['id'])
        if i.get('expectedness_basis'):
            basis=i['expectedness_basis']
            body+=prose(basis['explanation'],'small')+refs_html(basis['references'],evidence_context(saved['id'],'Expectedness',basis['explanation']))
        for c in i['claims']:
            body += '<div class="claim">'+prose(c['text'])+prose(c['evidence_class'].replace('_',' '),'small muted')
            if c['limitations']: body += prose(' '.join(c['limitations']),'limit prose')
            body += refs_html(c['references'],evidence_context(saved['id'],i['title'],c['text'],c['limitations']))+'</div>'
        if i['alternatives']: body += '<h3>Alternatives</h3>'+''.join(prose(x) for x in i['alternatives'])
        if i['open_questions']: body += '<h3>Missing evidence</h3>'+''.join(prose(x,'limit prose') for x in i['open_questions'])
        body += '<h3>Context and recovery</h3>'+refs_html(i['task_references']+i['recovery_references']+i['counterevidence'],evidence_context(saved['id'],i['title'],i['membership_basis'],i['open_questions']))
        if i.get('episode'):
            ep=i['episode']; context=evidence_context(saved['id'],i['title'],ep['intended_result'],ep['limitations'])
            content=prose(ep['intended_result'])+refs_html(ep['goal_references'],context)+prose(ep['membership_justification'])
            for attempt in ep['attempts']:
                content+='<h4>'+esc(attempt['role'].capitalize())+' · '+esc(attempt['key'])+'</h4>'+prose(attempt['description'])+prose(attempt['same_goal_basis'],'small')+refs_html([{'source_id':s} for s in attempt['event_ids']],{**context,'label':attempt['description'],'text':attempt['same_goal_basis']})
            content+=verification_html(ep['verification'],saved.get('episode_prerequisites',{}).get('verification'),context)
            for limit in ep['limitations']:content+=prose(limit,'limit small')
            resources=data.get('episode_resources',{}).get(saved['id'])
            if resources:
                content+=token_breakdown(resources['metrics'],'Resources associated with recovery')
                content+='<dl class="turn-metrics">'+''.join(metric_cell(k,l,resources['metrics'][k]) for k,l in (('llm_calls','Observed calls'),('tool_invocations','Tool invocations'),('recorded_tool_duration_ms','Recorded execution durations (ms)')))+'</dl>'
                content+=prose(resources['limitation'],'small muted')+detail('Selected identities, overlap and elapsed intervals',resources)
            body+=detail('Recovery episode',content,raw=True)
        if i.get('attribution'):
            a=i['attribution']; content=prose(a['category'].replace('_',' ')+' · '+a['support'].replace('_',' '),'meta')
            content+=prose(a['component']+' · '+a['version']+' · '+a['version_basis'].replace('_',' '),'small')+prose(a['basis'])
            content+=refs_html(a['component_references']+a['instruction_references']+a['execution_references'],evidence_context(saved['id'],'Fault attribution',a['basis'],a['alternatives']+a['missing_evidence']))
            content+='<h4>Immediate next action</h4>'+prose(a['immediate_next_action'])+'<h4>Persistent change basis</h4>'+prose(a['persistent_change_basis'])
            for limit in a['alternatives']+a['missing_evidence']:content+=prose(limit,'limit small')
            content+=detail('Attribution prerequisites',saved.get('attribution_prerequisites',{}))
            body+=detail('Fault attribution',content,raw=True)
        for p in data['recommendations']:
            if saved['id'] in p['recommendation']['incident_ids']:
                body += '<p><a data-proposal-link href="#'+esc(p['id'])+'">'+esc(p['recommendation']['title'])+'</a></p>'
        body += detail('Membership and saved review',saved)+'</dialog>'
    body += '<aside id="source-dialog" class="source-inspector" aria-labelledby="source-title" tabindex="-1" hidden><div class="dialog-head"><h2 id="source-title">Source</h2><div class="source-window-controls"><button data-source-expand class="link" aria-controls="source-dialog" aria-label="Expand source" aria-pressed="false" title="Expand source to full width">'+icon('external-link')+'<span>Expand</span></button><button data-source-close class="link" aria-controls="source-dialog" aria-label="Collapse source" title="Collapse source">'+icon('chevron-right')+'Collapse</button></div></div><button class="link" data-source-back hidden>Back to finding</button><div id="source-nav"></div><section id="source-relevance" aria-label="Why this source"></section><div class="source-record-head"><div><h3 id="source-kind"></h3><p id="source-time" class="meta"></p></div><button class="link" data-copy-source aria-label="Copy selected source">'+icon('copy')+'Copy</button></div><div id="source-panels"></div><div id="source-accounting"></div><p id="source-limit" class="limit small"></p><details id="source-context"><summary>Surrounding context</summary><div id="source-context-records"></div><div id="source-related"></div></details><details id="source-raw"><summary>Saved source and citation</summary><p id="source-meta" class="meta"></p><pre id="source-text" tabindex="0"></pre></details><details><summary>Source identity and disclosure</summary><pre id="source-identity"></pre></details></aside><div id="copy-status" role="status" aria-live="polite"></div>'
    body+=''.join('<template id="icon-'+name+'">'+icon(name)+'</template>' for name in (*REPORT_ICONS,*REPORT_WRAP_ICONS))
    css, js = REPORT_CSS, REPORT_JS
    payload = json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False,sort_keys=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    script_hash = base64.b64encode(hashlib.sha256(js.encode()).digest()).decode()
    csp = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'sha256-"+script_hash+"'; base-uri 'none'; form-action 'none'"
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="'+esc(csp)+'"><title>Ally · '+esc(title)+'</title><style>'+css+'</style></head><body'+(' class="library-embedded"' if embedded else '')+'>'+body+'<noscript>Enable JavaScript to open evidence and export. The saved findings and proposals remain in this document.</noscript><script type="application/json" id="report-data">'+payload+'</script><script>'+js+'</script><!-- Feather icons v4.29.1\n'+REPORT_ICON_LICENSE+'--></body></html>'


def export_session_investigation(store, investigation_id, destination, format='html', include_source_text=False, allow_content=False):
    if format not in ('html','json'): raise AnalyzerError('Format must be html or json')
    data = report_data(store,investigation_id,include_source_text,allow_content)
    content = render_report(data) if format=='html' else json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    path = Path(destination).expanduser().resolve(); path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('x',encoding='utf-8') as out: out.write(content)
        path.chmod(0o600)
    except FileExistsError: raise AnalyzerError('Refusing to overwrite an existing report')
    return {'path':str(path),'format':format,'investigation_id':investigation_id,
            'sha256':hashlib.sha256(content.encode()).hexdigest(),'model_text_edited':False,'source_text_included':include_source_text}
