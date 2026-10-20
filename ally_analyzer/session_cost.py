"""Source-session cost facts. Estimates and cumulative snapshots are never added."""
from decimal import Decimal, InvalidOperation

from .engine import price_response_components
from .pricing import configured_prices
from .session_scope import entities, get_scope, scope_rows
from .util import digest, timestamp


def captured_cost_fields(record):
    return {key: record[key] for key in ('totalCostUSD', 'startTime')
            if isinstance(record.get(key), (int, float)) and not isinstance(record[key], bool)
            and Decimal(str(record[key])).is_finite()}


def latest_snapshot(snapshots, provenance):
    """Prefer captured file order; timestamp-less records are common in native logs."""
    if not snapshots:
        return None, None
    common = set.intersection(*(set(provenance[event['id']]) for event, _ in snapshots))
    if common:
        winners = {max(snapshots, key=lambda item: provenance[item[0]['id']][path])[0]['id'] for path in common}
        if len(winners) == 1:
            return next(item for item in snapshots if item[0]['id'] in winners), sorted(common)[0]
    if len(snapshots) == 1:
        return snapshots[0], None
    times = [timestamp(event['timestamp']) for event, _ in snapshots]
    if all(value is not None for value in times) and times.count(max(times)) == 1:
        return snapshots[times.index(max(times))], None
    return None, None


def price_captured_responses(responses, prices, price_source):
    """Price one already reconciled population; never sum cumulative host snapshots."""
    components = [(r, price_response_components(r, prices)) for r in responses]
    priced = [(r, p['input'] + p['output'] if p is not None else None) for r, p in components]
    known = [(r, value) for r, value in priced if value is not None]
    estimate = {
        'value_usd': str(sum(value for _, value in known)) if known else None,
        'known_responses': len(known), 'eligible_responses': len(responses),
        'complete_for_captured_responses': bool(responses) and len(known) == len(responses),
        'price_book': {k: prices[k] for k in ('version', 'provider', 'effective_date')} if prices else None,
        'price_book_source': price_source,
        'response_ids': [r['id'] for r, _ in known],
        'source_ids': sorted({sid for r, _ in known for sid in r['evidence']}),
        'population': 'Main agent and structurally linked captured children; response identities counted once.',
    }
    estimate['components'] = {}
    for key in ('input', 'cached_input', 'output', 'reasoning_output'):
        values = [parts[key] for _, parts in components if parts is not None and parts[key] is not None]
        complete = bool(responses) and len(values) == len(responses)
        estimate['components'][key] = {
            'value_usd': str(sum(values)) if complete else None,
            'known_subtotal_usd': str(sum(values)) if values else None,
            'known_responses': len(values), 'eligible_responses': len(responses),
            'complete_for_captured_responses': complete,
        }
    estimate['component_definitions'] = {
        'input': 'Inclusive input cost: ordinary input, cache creation at its recorded TTL, and cache reads.',
        'cached_input': 'Cache-read cost, already included in input cost; not cache creation.',
        'output': 'Inclusive output cost, including separately recorded reasoning.',
        'reasoning_output': 'Recorded reasoning tokens priced at the output rate, already included in output cost.',
    }
    return estimate


def source_session_cost(store, run):
    scope = get_scope(store, run)
    prices, price_source = configured_prices(store.analysis(run['analysis_id'])['configuration'])
    responses = [r for r in entities(store, run, 'response') if r['eligible']]
    # Retained scopes predate geography normalization. Inspect only captured
    # numeric-usage metadata; do not mutate their response entities or prose.
    if prices.get('billing_rules'):
        from .session_scope import source_record
        restored = []
        for response in responses:
            if 'inference_geo' not in response:
                geos = set()
                for sid in response['evidence']:
                    record = source_record(store, run, sid)['record']
                    message = record.get('message')
                    usage = message.get('usage') if isinstance(message, dict) else None
                    if isinstance(usage, dict):
                        geo = usage.get('inference_geo') or 'global'
                        geos.add(geo if isinstance(geo, str) else 'unknown')
                response = {**response, 'inference_geo': next(iter(geos)) if len(geos) == 1 else 'unknown'}
            restored.append(response)
        responses = restored
    estimate = price_captured_responses(responses, prices, price_source)
    known = estimate['response_ids']
    rows = scope_rows(store, run)
    provenance = {r['id']: {} for r in rows}
    with store.connect() as db:
        for ref in db.execute('SELECT p.event_id,p.path,p.line FROM provenance p JOIN scope_events s ON s.event_id=p.event_id WHERE p.dataset_id=? AND s.scope_id=?', (scope['dataset_id'], run['scope_id'])):
            locations = provenance[ref['event_id']]
            locations[ref['path']] = max(ref['line'], locations.get(ref['path'], 0))
    snapshots = []
    invalid = 0
    for event in entities(store, run, 'lifecycle'):
        if event['kind'] != 'cost-state' or event['agent_id'] != 'main':
            continue
        raw_value = event.get('recorded_cost_estimate_usd')
        try:
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise ValueError()
            value = Decimal(str(raw_value))
            if not value.is_finite() or value < 0:
                raise ValueError()
        except (InvalidOperation, ValueError):
            invalid += 1
            continue
        snapshots.append((event, value))
    snapshot = None
    latest, member = latest_snapshot(snapshots, provenance)
    if latest:
        event, value = latest
        main_responses = [r for r in responses if r['agent_ids'] == ['main']]
        if member:
            comparable = [r for r in main_responses if all(member in provenance[sid] for sid in r['evidence'])]
            later = sum(any(provenance[sid][member] > provenance[event['id']][member] for sid in r['evidence']) for r in comparable)
            order_basis = 'Captured order in source member ' + digest(member)[:16]
        else:
            moment = timestamp(event['timestamp'])
            by_id = {r['id']: r for r in rows}
            comparable = [r for r in main_responses if moment is not None and all(timestamp(by_id[sid]['timestamp']) is not None for sid in r['evidence'])]
            later = sum(any(timestamp(by_id[sid]['timestamp']) > moment for sid in r['evidence']) for r in comparable)
            order_basis = 'Recorded timestamps' if moment is not None else 'Sole captured snapshot; relative response order unavailable'
        snapshot = {
            'value_usd': str(value), 'source_ids': event['evidence'],
            'timestamp': event['timestamp'], 'process_start_time': event.get('process_start_time'),
            'distinct_main_snapshots': len(snapshots),
            'later_main_responses': later, 'order_basis': order_basis,
            'response_order_coverage': {'comparable': len(comparable), 'main_responses': len(main_responses)},
            'population': 'Latest valid main-trace host cost snapshot; its billing scope is not independently verified.',
        }
    limitations = ['Estimates are not invoices. Source-agent cost is separate from the cost of running this analyzer.']
    if price_source['kind'] == 'bundled_verified':
        limitations.append('Token-price equivalent using public API rates verified ' + price_source['verified_on'] + '; excludes subscription billing and non-token fees. Historical billing rates are not independently verified.')
    if not prices:
        limitations.append('No pinned rate card supplied; captured token usage has not been priced.')
    elif len(known) != len(responses) or not responses:
        limitations.append('A complete rate and usage match is unavailable for some or all captured responses.')
    if scope['capture_gaps'].get('missing_child_traces'):
        limitations.append('Some child traces are unavailable; priced captured usage cannot establish the full task cost.')
    if snapshot:
        limitations.append('Host snapshots are cumulative estimates. Only the latest valid main-trace snapshot is shown; snapshots, response estimates and child totals are never added together.')
        if snapshot['later_main_responses']:
            count = snapshot['later_main_responses']
            limitations.append(str(count) + (' captured main-agent response follows' if count == 1 else ' captured main-agent responses follow') + ' the snapshot; it is not a final session total.')
        if snapshot['response_order_coverage']['comparable'] != snapshot['response_order_coverage']['main_responses']:
            limitations.append('Some response ordering relative to the snapshot is unavailable; snapshot freshness is not fully established.')
    elif snapshots:
        limitations.append('Multiple cost snapshots were captured, but their relative order cannot be established. No snapshot was selected as the latest.')
    if invalid:
        limitations.append(str(invalid) + ' invalid main-trace cost snapshots excluded.')
    return {'version': 'source-session-cost-v2', 'billing_scope': 'analyzed_session_only', 'priced_usage': estimate,
            'unavailable_child_traces': len({x['child_agent_id'] for x in scope['capture_gaps'].get('missing_child_traces', [])}),
            'recorded_snapshot': snapshot, 'limitations': limitations}


def cost_readout(cost):
    """Shared factual labels for HTML and Markdown, including retained old reports."""
    cost = cost or {}
    usage = cost.get('priced_usage', {})
    snapshot = cost.get('recorded_snapshot')
    if usage.get('value_usd') is not None:
        complete = usage.get('complete_for_captured_responses')
        kind = 'priced_usage' if complete else 'priced_subtotal'
        label = 'Your agent’s estimated cost' if complete else 'Your agent’s priced usage subtotal'
        basis = (str(usage['known_responses']) + ' of ' + str(usage['eligible_responses'])
                 + ' captured responses priced with the pinned rate card. ' + usage['population'])
        if not complete:
            basis += ' Partial subtotal; full cost is unknown.'
        if cost.get('unavailable_child_traces'):
            basis += ' Some child traces are unavailable; full task cost is unknown.'
        value = money(usage['value_usd'])
    elif snapshot:
        kind = 'recorded_snapshot'
        label = 'Your agent’s recorded cost estimate'
        value = money(snapshot['value_usd'])
        basis = ('Latest valid host snapshot' + (' at ' + snapshot['timestamp'] if snapshot.get('timestamp') else '')
                 + '; cumulative estimate, not a verified final session total.')
        if snapshot['later_main_responses']:
            count = snapshot['later_main_responses']
            basis += ' ' + str(count) + (' captured main-agent response follows' if count == 1 else ' captured main-agent responses follow') + ' this snapshot.'
        order = snapshot['response_order_coverage']
        if order['comparable'] != order['main_responses']:
            basis += ' Freshness is not fully established.'
    else:
        kind = 'unavailable'
        label, value = 'Your agent’s cost', 'Unavailable'
        basis = ('No usable cost snapshot or priced captured usage is available. Missing cost is unknown, not zero.' if cost else
                 'Cost accounting is not included in this saved report. Re-export from its investigation store to calculate it; unknown cost is not zero.')
    return {'kind': kind, 'label': label, 'value': value, 'basis': basis,
            'limitations': cost.get('limitations', ['Estimates are not invoices. Source-agent cost is separate from analyzer cost.']),
            'source_ids': usage.get('source_ids', []) if usage.get('value_usd') is not None else (snapshot['source_ids'] if snapshot else [])}


def compact_cost(cost):
    usage = cost['priced_usage']
    origin = usage.get('price_book_source', {})
    origin = {**{k:v for k,v in origin.items() if k != 'sources'},
              **({'source_count': len(origin['sources']), 'source_preview': origin['sources'][:1]} if 'sources' in origin else {})}
    return {**cost, 'priced_usage': {**{k:v for k,v in usage.items() if k not in ('response_ids', 'source_ids')},
            'price_book_source': origin,
            'source_count': len(usage['source_ids']), 'source_preview': usage['source_ids'][:5],
            'continuation': 'Page captured responses with get_investigation_records; inspect numeric usage with inspect_response_accounting.'}}


def money(value):
    amount = Decimal(value)
    return '<$0.01' if 0 < amount < Decimal('.01') else '$' + format(amount, ',.2f')
