"""A cost-and-usage opening over recorded accounting, never an authored finding."""
import re

from .session_cost import cost_readout


def developer_readout(cost, metrics):
    display = cost_readout(cost)
    fields = {'input_tokens': 'prompt_tokens', 'cached_input_tokens': 'cached_tokens',
              'output_tokens': 'completion_tokens', 'reasoning_output_tokens': 'thinking_tokens'}
    usage = {}
    for name, key in fields.items():
        metric = metrics.get(key, {})
        # An empty or missing population does not establish zero usage.
        known = bool(metric.get('eligible')) and metric.get('value') is not None
        usage[name] = {k: metric.get(k) for k in ('definition_id', 'known', 'eligible', 'known_subtotal')}
        usage[name]['value'] = metric['value'] if known else None
    def pair(total, subset, total_label, subset_label):
        whole, part = usage[total]['value'], usage[subset]['value']
        text = format(whole, ',') + ' ' + total_label if whole is not None else total_label + ' unavailable'
        if whole is not None and part is not None:
            return text + ', including ' + format(part, ',') + ' ' + subset_label
        return text + '; ' + (subset_label + ' unavailable' if part is None else format(part, ',') + ' ' + subset_label + ' recorded')
    tokens = (pair('input_tokens', 'cached_input_tokens', 'input tokens', 'cached input tokens') + '; '
              + pair('output_tokens', 'reasoning_output_tokens', 'output tokens', 'reasoning tokens'))
    if display['kind'] == 'unavailable':
        opening = 'Session cost is unavailable (' + tokens + ').'
    elif display['kind'] == 'priced_subtotal':
        opening = 'Priced usage subtotal: ' + display['value'] + ' (' + tokens + '); full session cost is unknown.'
    else:
        opening = 'You spent approximately ' + display['value'] + ' (' + tokens + ') on this session.'
    qualifications = []
    if display['kind'] == 'recorded_snapshot':
        qualifications.append('Cost is the latest recorded host estimate; final session cost is unverified.')
        snapshot = cost['recorded_snapshot']
        later = snapshot['later_main_responses']
        if later:
            qualifications.append('The cost snapshot precedes ' + str(later) + ' later captured main-agent response' + ('.' if later == 1 else 's.'))
    if cost and cost.get('unavailable_child_traces'):
        qualifications.append('Some child traces are unavailable; these captured totals do not establish the full task cost or usage.')
    return {'version': 'developer-readout-v1', 'opening': opening, 'token_summary': tokens, 'usage': usage,
            'population': 'Main agent and structurally linked captured children; reconciled identities counted once.',
            'cost_kind': display['kind'], 'qualifications': qualifications,
            'default_reply_policy': {'first': 'opening', 'then': ['recommendations_or_outcome', 'decisive_evidence', 'concrete_changes_when_supported'],
                'cache_and_compaction': 'Only when the current user asks, except cached-input count in the opening. This applies to evidence summaries, caveats, checks and copy-paste prompts too.',
                'retain_underlying_analysis_and_tools': True},
            'input_includes_cached': True, 'output_includes_reasoning': True}


TOPIC_PATTERNS = {
    'cache': r'(?<![a-z])(?:cache[-_ ](?:reads?|writes?|creation|hit[-_ ](?:rate|share))|cached[-_ ]input|prompt[-_ ]cach\w*|promptCacheTtl|subagentPromptCacheTtl)(?![a-z])',
    'compaction': r'compact_boundary|compactMetadata|preTokens|postTokens|\b(?:context|conversation|session|harness)\b.{0,64}\bcompaction\b|\bcompaction\b.{0,64}\b(?:events?|boundary|tokens?|context|instructions?|authorization|session)\b',
}
REQUEST_PATTERNS = {'cache': r'cache|cached|caching|promptCacheTtl', 'compaction': r'compaction|compacting|compacted|compact_boundary'}


def prepare_session_reply(store, investigation_id, body, requested_details=None, detail_request=None):
    """Validate a new authored draft, without editing it or any saved judgment."""
    from .session_investigation import accounting
    from .session_cost import source_session_cost
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
    readout = developer_readout(source_session_cost(store, run), accounting(store, run)['session'])
    issues = [{'code': 'unrequested_' + topic + '_detail', 'topic': topic,
               'message': 'Revise your new default draft to omit unrequested ' + topic + ' detail, including caveats, checks and snippets. Retain the underlying analysis.'}
              for topic, pattern in TOPIC_PATTERNS.items() if topic not in details and re.search(pattern, body, re.I)]
    if body.lstrip().startswith(readout['opening']):
        issues.append({'code': 'opening_repeated', 'message': 'Supply only the authored body; the computed opening is prepended once.'})
    request_id = log_access(store, run, 'prepare_session_reply',
        {'body_sha256': digest(body), 'requested_details': details, 'issue_codes': [i['code'] for i in issues]}, [])
    result = {'request_id': request_id, 'status': 'needs_revision' if issues else 'ready', 'issues': issues,
              'session_readout': readout,
              'validation_limit': 'Mechanical wording and accounting checks only; not a factual or semantic-quality certificate. No saved judgments or supplied prose were changed.'}
    if not issues:
        result['reply'] = '\n\n'.join([readout['opening'], *readout['qualifications'], body])
    return result
