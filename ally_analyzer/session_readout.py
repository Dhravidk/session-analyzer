"""A cost-and-usage opening over recorded accounting, never an authored finding."""
import re
from decimal import Decimal

from .session_cost import cost_readout, money


def developer_readout(cost, metrics):
    display = cost_readout(cost)
    fields = {'input_tokens': 'prompt_tokens', 'cached_input_tokens': 'cached_tokens',
              'output_tokens': 'completion_tokens', 'reasoning_output_tokens': 'thinking_tokens'}
    usage = {}
    components = (cost or {}).get('priced_usage', {}).get('components', {})
    for name, key in fields.items():
        metric = metrics.get(key, {})
        # An empty or missing population does not establish zero usage.
        known = bool(metric.get('eligible')) and metric.get('value') is not None
        usage[name] = {k: metric.get(k) for k in ('definition_id', 'known', 'eligible', 'known_subtotal')}
        usage[name]['value'] = metric['value'] if known else None
        component = components.get(name[:-7], {})
        usage[name]['cost_usd'] = component.get('value_usd')
        usage[name]['cost_coverage'] = {k: component.get(k) for k in ('known_responses', 'eligible_responses')}
    def amount(name):
        value = usage[name]['cost_usd']
        if value is None:
            return 'cost unavailable'
        value = Decimal(value)
        # Tiny known costs must remain visible, rather than rounding to zero.
        return '$' + (format(value, ',.2f') if value == 0 or value >= Decimal('.01')
                      else format(value, 'f').rstrip('0').rstrip('.'))
    def pair(total, subset, total_label, subset_label):
        whole, part = usage[total]['value'], usage[subset]['value']
        text = format(whole, ',') + ' ' + total_label if whole is not None else total_label + ' unavailable'
        if whole is not None and part is not None:
            return text + ' / ' + amount(total) + ', including ' + format(part, ',') + ' ' + subset_label + ' / ' + amount(subset)
        return text + ' / ' + amount(total) + '; ' + (subset_label + ' unavailable' if part is None else format(part, ',') + ' ' + subset_label + ' recorded') + ' / ' + amount(subset)
    tokens = (pair('input_tokens', 'cached_input_tokens', 'input tokens', 'cached input tokens') + '; '
              + pair('output_tokens', 'reasoning_output_tokens', 'output tokens', 'reasoning tokens'))
    if display['kind'] == 'unavailable':
        opening = 'Session cost is unavailable (' + tokens + ').'
    elif display['kind'] == 'priced_subtotal':
        opening = 'Priced usage subtotal: ' + display['value'] + ' (' + tokens + '); full session cost is unknown.'
    elif display['kind'] == 'priced_usage':
        opening = 'Estimated session cost: ' + display['value'] + ' (' + tokens + ').'
    else:
        opening = 'You spent approximately ' + display['value'] + ' (' + tokens + ') on this session.'
    qualifications = []
    price_source = (cost or {}).get('priced_usage', {}).get('price_book_source', {})
    if display['kind'] in ('priced_usage', 'priced_subtotal') and price_source.get('kind') == 'bundled_verified':
        qualifications.append('Token estimate at public API rates verified ' + price_source['verified_on'] + '; not a subscription charge. Analyzer/reviewer usage is excluded.')
    snapshot = (cost or {}).get('recorded_snapshot')
    if display['kind'] == 'priced_usage' and snapshot and money(snapshot['value_usd']) != display['value']:
        later = snapshot['later_main_responses']
        age = ' (before ' + str(later) + ' later response' + ('s)' if later != 1 else ')') if later else ''
        qualifications.append('The log’s separate host estimate is ' + money(snapshot['value_usd']) + age + '; its billing scope and reconciliation with this token estimate are unverified.')
    if display['kind'] == 'recorded_snapshot':
        qualifications.append('Cost is the latest recorded host estimate; final session cost is unverified.')
        snapshot = cost['recorded_snapshot']
        later = snapshot['later_main_responses']
        if later:
            qualifications.append('The cost snapshot precedes ' + str(later) + ' later captured main-agent response' + ('.' if later == 1 else 's.'))
    if cost and cost.get('unavailable_child_traces'):
        qualifications.append('Some child traces are unavailable; these captured totals do not establish the full task cost or usage.')
    return {'version': 'developer-readout-v4', 'opening': opening, 'token_summary': tokens, 'usage': usage,
            'billing_scope': 'analyzed_session_only',
            'population': 'Main agent and structurally linked captured children; reconciled identities counted once.',
            'cost_kind': display['kind'], 'qualifications': qualifications,
            'default_reply_policy': {'first': 'opening', 'then': ['recommendations_or_outcome', 'task_outcome_and_instruction_following', 'decisive_evidence', 'concrete_changes_when_supported'],
                'compliance': 'Give separate authored assessments of delivery and adherence to evidenced instructions. Cite decisive requests/actions; preserve unmet versus unverified and later recovery. Do not invent a violation or approval gate.',
                'cache_and_compaction': 'Only when the current user asks, except cached-input count and cost in the opening. This applies to evidence summaries, caveats, checks and copy-paste prompts too.',
                'retain_underlying_analysis_and_tools': True},
            'input_includes_cached': True, 'output_includes_reasoning': True}


TOPIC_PATTERNS = {
    'cache': r'(?<![a-z])(?:cache[-_ ](?:reads?|writes?|creation|hit[-_ ](?:rate|share))|cached[-_ ]input|prompt[-_ ]cach\w*|promptCacheTtl|subagentPromptCacheTtl)(?![a-z])',
    'compaction': r'compact_boundary|compactMetadata|preTokens|postTokens|(?<![\w/])/compact\b|\b(?:after|before|during)\s+(?:(?:a|the|manual|automatic)\s+){0,2}compaction\b|\b(?:context|conversation|session|harness)\b.{0,64}\bcompaction\b|\bcompaction\b.{0,64}\b(?:events?|boundary|tokens?|context|instructions?|authorization|session)\b',
}
REQUEST_PATTERNS = {'cache': r'cache|cached|caching|promptCacheTtl', 'compaction': r'compaction|compacting|compacted|compact_boundary'}


def prepare_session_reply(store, investigation_id, body, requested_details=None, detail_request=None, compliance=None, allow_content=False):
    """Validate a new authored draft, without editing it or any saved judgment."""
    from .session_investigation import accounting
    from .session_cost import source_session_cost
    from .session_review import request_coverage
    from .session_scope import get_run, log_access
    from .util import AnalyzerError, digest
    details = requested_details or []
    if not isinstance(body, str) or not body.strip() or len(body) > 30000:
        raise AnalyzerError('Reply body must be nonblank text of at most 30000 characters')
    if len(set(details)) != len(details) or set(details) - TOPIC_PATTERNS.keys():
        raise AnalyzerError('Requested details must be unique cache/compaction topics')
    if details and (not isinstance(detail_request, str) or any(
            not re.search(REQUEST_PATTERNS[topic], detail_request, re.I) for topic in details)):
        raise AnalyzerError('Quote the current user request explicitly asking for each requested detail topic; archived text is not a request')
    run = get_run(store, investigation_id)
    coverage = request_coverage(store, run)
    coverage = {**coverage, 'unread_request_count': len(coverage['unread_requests']),
                'unread_requests': coverage['unread_requests'][:8]}
    readout = developer_readout(source_session_cost(store, run), accounting(store, run)['session'])
    issues = [{'code': 'unrequested_' + topic + '_detail', 'topic': topic,
               'message': 'Revise your new default draft to omit unrequested ' + topic + ' detail, including caveats, checks and snippets. Retain the underlying analysis.'}
              for topic, pattern in TOPIC_PATTERNS.items() if topic not in details and re.search(pattern, body, re.I)]
    if body.lstrip().startswith(readout['opening']):
        issues.append({'code': 'opening_repeated', 'message': 'Supply only the authored body; the computed opening is prepended once.'})
    if not details and len(body.split()) > 450:
        issues.append({'code': 'default_reply_too_long',
                       'message': 'Keep the default body within 450 words. Preserve the recommendation, two assessments, decisive evidence and material limits; omit incidental counts and a separate chronology. Full saved evidence/reports are unchanged; focused detailed follow-ups can answer directly.'})
    # These are exact spans from the model's own reply, not generated verdicts.
    # Presence checks cannot establish whether the assessments are true.
    if compliance is not None and (not isinstance(compliance, dict)
            or set(compliance) != {'task_outcome', 'instruction_following'}
            or any(not isinstance(v, str) or not v.strip() or len(v) > 4000 for v in compliance.values())):
        raise AnalyzerError('Compliance must contain task_outcome and instruction_following text, each nonblank and at most 4000 characters')
    for aspect in ('task_outcome', 'instruction_following'):
        assessment = (compliance or {}).get(aspect)
        if not assessment or assessment not in body:
            issues.append({'code': 'missing_' + aspect + '_assessment',
                           'message': 'Include your evidence-backed ' + aspect + ' assessment in the reply body and supply that exact text in compliance. State unavailable evidence instead of inventing a verdict.'})
    if compliance and compliance['task_outcome'] == compliance['instruction_following']:
        issues.append({'code': 'undifferentiated_compliance_assessments',
                       'message': 'Assess delivery and instruction following separately; the same text cannot stand for both.'})
    if allow_content and coverage['unread_request_count']:
        issues.append({'code': 'unread_task_requests',
                       'message': 'Before a whole-session compliance readout, fully read the remaining captured main-task requests, including continuations. request_coverage gives the next source IDs; refresh the overview for more. This does not require reading every assistant step or creating a saved report.'})
    request_id = log_access(store, run, 'prepare_session_reply',
        {'body_sha256': digest(body), 'requested_details': details, 'issue_codes': [i['code'] for i in issues]}, [])
    result = {'request_id': request_id, 'status': 'needs_revision' if issues else 'ready', 'issues': issues,
              'session_readout': readout,
              'request_coverage': coverage,
              'validation_limit': 'Mechanical presence, wording and accounting checks only; not a factual or semantic-quality certificate. Compliance assessments are authored by the model, not inferred by this tool. No saved judgments or supplied prose were changed.'}
    if compliance is not None:
        result['authored_compliance'] = dict(compliance)
    if not issues:
        result['reply'] = '\n\n'.join([readout['opening'], *readout['qualifications'], body])
    return result
