"""Markdown reading export over saved data; no model calls or source rereads.

Standalone HTML embeds a render plan, referencing its existing source strings
instead of duplicating large results. The library and CLI use the same plan.
"""
import hashlib
import html
import json
import re

from .session_finding_links import finding_links
from .session_reading import REQUIREMENT_STATUS, current_review, remaining_work_text
from .session_story import saved_source_explanation


def text(value):
    """Display saved prose literally, including Markdown/HTML punctuation."""
    value = html.escape(str(value), quote=False)
    return re.sub(r'([\\`*_{}\[\]()#+.!|>~-])', r'\\\1', value)


def anchor(identity):
    return 'source-' + hashlib.sha256(str(identity).encode()).hexdigest()[:24]


def fence(value, language='text'):
    delimiter = '`' * max(3, 1 + max((len(x) for x in re.findall(r'`+', value)), default=0))
    return delimiter + language + '\n', ('\n' if not value.endswith('\n') else '') + delimiter + '\n\n'


def markdown_parts(data):
    """Return strings and exact source-field references; never modify data."""
    parts = []
    sources = data.get('sources', {})
    referenced = set()

    def add(value=''):
        parts.append(value)

    def paragraph(value):
        if value is not None and value != '': add(text(value) + '\n\n')

    def heading(label, level=2): add('#' * level + ' ' + text(label) + '\n\n')

    def code(value, language='text'):
        opening, closing = fence(value, language)
        add(opening + value + closing)

    def details(label, value):
        if value is None: return
        add('<details>\n<summary>' + html.escape(label) + '</summary>\n\n')
        code(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False, sort_keys=True), 'json')
        add('</details>\n\n')

    def link(sid, label=None):
        referenced.add(sid)
        return '[' + text(label or sid) + '](#' + anchor(sid) + ')'

    def refs(values, owner=None):
        for ref in values or []:
            sid = ref['source_id']
            location = sid
            if ref.get('start_char') is not None:
                location += ':' + str(ref['start_char']) + '–' + str(ref.get('end_char', '?'))
            explanation, verdict = saved_source_explanation(ref, data, {'owner_id':owner})
            label = explanation or location
            add('- ' + link(sid, label) + (' · ' + text(location) if label != location else '') + '\n')
            if verdict and verdict != 'supported': add('  Saved review: ' + text(verdict) + '\n')
        if values: add('\n')

    def authored(value, owner=None):
        if not value: return
        if isinstance(value, str): paragraph(value); return
        paragraph(value.get('text'))
        if value.get('evidence_class'): paragraph('Evidence class: ' + value['evidence_class'])
        refs(value.get('references'), owner)
        for limit in value.get('limitations', []): paragraph(limit)

    def review(record_id):
        check = current_review(data, record_id)
        if check:
            paragraph('Claude review: ' + check['verdict'])
            paragraph(check.get('assessment'))
            for limit in check.get('remaining_uncertainty', []): paragraph(limit)
            details('Complete saved review', check)
        elif data['investigation'].get('review_workflow'):
            paragraph('Claude review: not saved')

    labels = {'prompt_tokens':'Input total', 'uncached_input_tokens':'Uncached input',
              'cache_creation_tokens':'Cache write', 'cached_tokens':'Cache read',
              'completion_tokens':'Output', 'thinking_tokens':'Thinking (included in output)',
              'llm_calls':'Observed LLM calls', 'tool_invocations':'Tool invocations',
              'session_duration_minutes':'Observed span (min)', 'turn_duration_seconds':'Recorded duration (s)',
              'observed_turn_span_seconds':'Observed span (s)'}

    def metrics(values):
        add('| Metric | Value | Coverage |\n| --- | ---: | --- |\n')
        for key in [k for k in labels if k in values] + sorted(set(values) - set(labels)):
            metric = values[key]
            value = metric.get('value')
            shown = str(value) if value is not None else 'Unknown'
            coverage = []
            if metric.get('eligible') is not None:
                coverage.append(str(metric.get('known', '?')) + '/' + str(metric['eligible']) + ' recorded')
            if value is None and metric.get('known_subtotal') is not None:
                coverage.append('Known subtotal ' + str(metric['known_subtotal']))
            if metric.get('unavailable_reason'): coverage.append(metric['unavailable_reason'])
            if metric.get('population_status') == 'empty_population': coverage.append('Empty population; completeness not established')
            add('| ' + text(labels.get(key, key.replace('_', ' '))) + ' | ' + text(shown) + ' | '
                + text('; '.join(coverage)) + ' |\n')
        add('\n')
        details('Exact measurements, definitions and identities', values)

    run = data['investigation']
    latest = run.get('review_workflow', {}).get('latest_draft_id')
    draft = next((r for r in data.get('conclusion_drafts', []) if r['id'] == latest), None)
    owner = latest if draft and all(draft['conclusion'].get(k) == run.get(k) for k in ('synopsis','observed_outcome','summary')) else None
    heading(run.get('title') or 'Session ' + run['root_session_id'], 1)
    paragraph('Investigation: ' + run['run_status'])
    paragraph('Session: ' + run['root_session_id'] + ' · Analysis: ' + run['id'])
    paragraph('Saved analysis time: ' + str(run.get('finished_at') or run.get('created_at') or 'Unknown'))
    authored(run.get('synopsis') or run.get('summary'), owner)
    if not run.get('synopsis') and not run.get('summary'): paragraph('No session synopsis has been saved.')
    heading('Outcome')
    authored(run.get('observed_outcome'), owner)
    if not run.get('observed_outcome'): paragraph('No observed outcome has been saved.')
    if run.get('stop_reason'): paragraph(run['stop_reason'])
    for question in run.get('unresolved_questions', []): paragraph(question)
    if owner:
        review(latest)
    elif draft and run['run_status'] in ('partial','failed'):
        heading('Latest Claude draft · not finalized', 3)
        paragraph(draft['conclusion'].get('title'))
        paragraph(draft['conclusion'].get('summary'))
        details('Saved draft and status', draft)

    remaining = remaining_work_text(data)
    if remaining:
        heading('Remaining work and evidence')
        code(remaining)

    main = data.get('main_accounting', data['accounting'])
    heading('Main-agent metrics')
    paragraph('Input total includes uncached input, cache write and cache read. Thinking is included in output when reported that way by the provider. Observed spans are not active-work durations.')
    metrics(main.get('session', {}))
    paragraph(main.get('limitations'))

    heading('Requirements')
    mapped = data.get('requirement_map')
    if not mapped: paragraph('No requirement map has been saved. Inventory coverage is not established.')
    else:
        body = mapped['requirement_map']
        paragraph(body['scope']); paragraph('Inventory: ' + body['inventory_status'])
        for limit in body['limitations']: paragraph(limit)
        review(mapped['id'])
        for item in body['requirements']:
            heading(item['description'], 3)
            paragraph(REQUIREMENT_STATUS.get(item['status'], item['status']))
            paragraph(item['scope']); paragraph(item['status_basis'])
            refs(item['intent_references'] + item['result_references'], mapped['id'])
            for limit in item['missing_evidence']: paragraph(limit)
            details('Requirement, verification, revision and intent changes', item)
        details('Request coverage and inventory prerequisites', {k:v for k,v in mapped.items() if k != 'requirement_map'})

    navigation = [(saved, finding_links(data, saved)) for saved in data.get('incidents', [])]
    heading('Turns')
    for index, turn in enumerate(main.get('turns', []), 1):
        heading('Turn ' + str(index), 3)
        sid = turn.get('request_event_id')
        if sid:
            add(link(sid, 'Full request') + '\n\n')
            value = sources.get(sid, {}).get('text')
            if value: paragraph(value[:180] + ('…' if len(value) > 180 else ''))
        for saved, links in navigation:
            association = links.get(turn['id'])
            if not association: continue
            guide = saved['incident'].get('reader_guide', {})
            for event in association.get('events', []):
                add('- ' + link(event['primary_source_id'], event['title']) + '\n')
            add('\n[Complete finding: ' + text(guide.get('name') or saved['incident']['title'])
                + '](#' + anchor(saved['id']) + ')\n\n')
        metrics(turn.get('metrics', {}))
        details('Turn identities and attribution', {k:v for k,v in turn.items() if k != 'metrics'})

    heading('Findings')
    if not data.get('incidents'): paragraph('No findings saved. Investigation status: ' + run['run_status'] + '.')
    for index, saved in enumerate(data.get('incidents', []), 1):
        incident = saved['incident']; guide = incident.get('reader_guide')
        add('<a id="' + anchor(saved['id']) + '"></a>\n\n')
        heading(guide['name'] if guide else incident['title'], 3)
        paragraph('F' + str(index))
        if guide:
            paragraph(guide['takeaway']); refs(guide['references'], saved['id'])
            for limit in guide['limitations']: paragraph(limit)
        review(saved['id'])
        if guide:
            heading('What happened', 4)
            for event in guide['events']:
                heading(event['title'], 5)
                paragraph(event['explanation'])
                add(link(event['primary_source_id'], 'Decisive source') + '\n\n')
                refs(event['references'], saved['id'])
                for limit in event['limitations']: paragraph(limit)
        else:
            paragraph(incident.get('membership_basis'))
            paragraph('No local event explanation was saved for this finding.')
        for claim in incident.get('claims', []): authored(claim, saved['id'])
        for limit in incident.get('open_questions', []): paragraph(limit)
        details('Complete finding, classifications and episode membership', saved)
        if saved['id'] in data.get('episode_resources', {}):
            details('Resources associated with recovery · deduplicated identities', data['episode_resources'][saved['id']])

    heading('Proposed changes')
    if not data.get('recommendations'):
        paragraph('No recommendations saved. Investigation status: ' + run['run_status'] + '.')
    for saved in data.get('recommendations', []):
        proposal = saved['recommendation']; heading(proposal['title'], 3)
        paragraph('Target: ' + proposal['target_kind'])
        edit = proposal.get('edit')
        if edit:
            for key in ('target_path','scope','location','operation'): paragraph(edit.get(key))
            if edit.get('original_text') is not None:
                heading('Original text or insertion anchor', 4); code(edit['original_text'])
            heading('Invocation' if edit['operation']=='invoke' else 'Replacement text', 4)
            code(edit.get('invocation', '') if edit['operation']=='invoke' else edit.get('replacement_text', ''))
        review(saved['id'])
        details('Saved proposal and qualifications', saved)
        details('Validation and readiness', data.get('validation', {}).get(saved['id']))
        details('Target inspection and net growth', data.get('edit_inspection', {}).get(saved['id']))

    heading('Recorded failures')
    details('Explanation coverage', data.get('failure_explanation_coverage'))
    for saved in data.get('failure_explanations', []): details('Saved failure explanation', saved)
    heading('Subagents')
    children = [data['agents'][aid] for aid in sorted(data.get('agents', {})) if aid != 'main']
    if not children: paragraph('No child-agent records are included; see capture gaps for unavailable traces.')
    for agent in children:
        heading(agent['agent_id'], 3); paragraph('Trace: ' + agent['trace_status'])
        if agent.get('metrics'): metrics(agent['metrics'])
        details('Child identity and linkage', {k:v for k,v in agent.items() if k != 'metrics'})
    details('Subagent invocations and parent-reported summaries', data.get('delegations', []))

    heading('Coverage and measurements')
    paragraph(run.get('coverage_explanation'))
    details('Captured scope and missing traces', data.get('scope'))
    heading('Combined main and captured child usage', 3)
    metrics(data['accounting'].get('session', {}))
    paragraph(data['accounting'].get('limitations'))
    details('Attribution coverage', data['accounting'].get('attribution_coverage'))
    heading('Analyzer usage · separate from the source session', 3)
    details('Exact host usage and provenance', run.get('analyzer_usage'))
    for key, label in (('turn_patterns','Turn patterns'),('resource_views','Context/cache and tool-output measurements'),
                       ('measurements','Registered measurements'),('response_usage','Response usage and thinking-token availability'),
                       ('report_checks','Report checks'),('exposure','Investigator evidence coverage')):
        details(label, data.get(key))

    # References to unavailable sources still have a target and an explicit state.
    heading('Sources')
    paragraph('Exact retained masked text. Source identity, omission reasons and usage associations remain separate. Thinking text is not evidence that an action executed.')
    ordered_sources = sorted(sources, key=lambda sid:(sources[sid].get('agent_id') != 'main',
                             sources[sid].get('agent_id') or '', sources[sid].get('timestamp') or '', sid))
    for sid in ordered_sources + sorted(referenced - set(sources)):
        source = sources.get(sid, {})
        add('<a id="' + anchor(sid) + '"></a>\n\n')
        heading(sid, 3)
        paragraph(' · '.join(str(source[k]) for k in ('role','agent_id','timestamp') if source.get(k)))
        value = source.get('text')
        if isinstance(value, str) and value:
            opening, closing = fence(value)
            add(opening); parts.append({'source_id':sid}); add(closing)
        elif isinstance(value, str): paragraph('The saved evidence projection is empty. See the recorded omission reasons below.')
        else: paragraph('Source text was not included in this export. This does not establish that the source was empty.')
        metadata = {k:v for k,v in source.items() if k != 'text'}
        content = source.get('content_metadata') or {}
        thinking = content.get('thinking_text', [])
        for index, block in enumerate(thinking):
            heading('Captured thinking · not execution evidence', 4)
            opening, closing = fence(block['text'])
            add(opening); parts.append({'source_id':sid, 'thinking_index':index}); add(closing)
        if thinking:
            metadata['content_metadata'] = {**content, 'thinking_text':[
                {k:v for k,v in block.items() if k != 'text'} for block in thinking]}
        details('Source identity, disclosure and content metadata', metadata)

    heading('Saved analysis provenance')
    details('Investigation and workflow state', run)
    paragraph(data.get('rendering_contract'))
    return parts


def render_markdown(data):
    def resolve(part):
        if isinstance(part, str): return part
        source = data['sources'][part['source_id']]
        return (source['content_metadata']['thinking_text'][part['thinking_index']]['text']
                if 'thinking_index' in part else source['text'])
    return ''.join(resolve(part) for part in markdown_parts(data))
