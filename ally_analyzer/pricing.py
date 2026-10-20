"""Offline, versioned public-rate selection; no model or network calls."""
from decimal import Decimal, InvalidOperation
from datetime import date
from pathlib import Path

from .util import AnalyzerError, digest, integer, strict_json

RATE_KEYS = ('input_per_million', 'output_per_million', 'cache_read_per_million',
             'cache_write_5m_per_million', 'cache_write_1h_per_million')


def resolve_prices(prices=None):
    from .engine import validate_prices
    if prices is not None:
        return validate_prices(prices), {'kind': 'explicit', 'basis': 'Operator-supplied rate card'}
    try:
        book = strict_json(Path(__file__).with_name('verified_prices.json').read_text())
    except (OSError, ValueError) as exc:
        raise AnalyzerError('Bundled verified pricing is unavailable; restore the complete package or supply an explicit rate card') from exc
    validate_prices(book)
    try:
        date.fromisoformat(book['verified_on'])
    except (KeyError, TypeError, ValueError):
        raise AnalyzerError('Bundled pricing needs an ISO verification date')
    if (book.get('currency') != 'USD' or not isinstance(book.get('sources'), list) or not book['sources']
            or any(not isinstance(url, str) or not url.startswith('https://platform.claude.com/') for url in book['sources'])):
        raise AnalyzerError('Bundled pricing needs its verification date and primary sources')
    return book, {'kind': 'bundled_verified', 'verified_on': book['verified_on'],
                  'catalog_sha256': digest(book), 'sources': book['sources'],
                  'basis': 'Public API token-price equivalent at the verified snapshot, not subscription billing or an invoice'}


def configured_prices(configuration):
    """Preserve pinned overrides; older unpriced scopes can query new facts."""
    book = configuration.get('price_book')
    if book is None:
        return resolve_prices()
    from .engine import validate_prices
    return validate_prices(book), configuration.get('price_book_source', {'kind': 'explicit'})


def validate_billing_rules(book):
    rules = book.get('billing_rules')
    if rules is None:
        return
    if not isinstance(rules, dict) or set(rules) != {'us_inference_models', 'us_inference_multiplier', 'context_tiers', 'fast_multipliers'}:
        raise AnalyzerError('Billing rules need exact geography, context-tier and fast-mode policies')
    models = set(book['rates'])
    us = rules['us_inference_models']
    if not isinstance(us, list) or any(not isinstance(v, str) for v in us) or len(us) != len(set(us)) or set(us) - models:
        raise AnalyzerError('Geography rules must name unique declared models')
    for key in ('context_tiers', 'fast_multipliers', 'us_inference_multiplier'):
        entries = rules[key] if key != 'us_inference_multiplier' else {model: rules[key] for model in us}
        if not isinstance(entries, dict) or set(entries) - models:
            raise AnalyzerError('Billing modifiers must name declared models')
        for entry in entries.values():
            value = entry
            if key == 'context_tiers':
                if (not isinstance(entry, dict) or set(entry) != {'above_input_tokens', 'multiplier'}
                        or not integer(entry['above_input_tokens']) or entry['above_input_tokens'] == 0):
                    raise AnalyzerError('Context-tier rules need a positive input threshold and multiplier')
                value = entry['multiplier']
            try:
                number = Decimal(str(value))
                if isinstance(value, bool) or not number.is_finite() or number <= 0:
                    raise ValueError()
            except (ValueError, InvalidOperation):
                raise AnalyzerError('Billing multipliers must be finite positive decimals')


def response_rate(response, book):
    if not book or len(response['models']) != 1:
        return None
    model = response['models'][0]
    base = book['rates'].get(model)
    if not base or base['service_tier'] != response['service_tier']:
        return None
    rules, factor = book.get('billing_rules'), Decimal(1)
    if base['speed'] != response['speed']:
        fast = (rules or {}).get('fast_multipliers', {}).get(model)
        if base['speed'] != 'standard' or response['speed'] != 'fast' or fast is None:
            return None
        factor *= Decimal(str(fast))
    if rules:
        geo = response.get('inference_geo')
        if geo == 'us' and model in rules['us_inference_models']:
            factor *= Decimal(str(rules['us_inference_multiplier']))
        elif geo not in (None, '', 'global'):
            return None
        tier = rules['context_tiers'].get(model)
        if tier:
            total = response['tokens'].get('total_input_tokens')
            if not integer(total):
                return None
            if total > tier['above_input_tokens']:
                factor *= Decimal(str(tier['multiplier']))
    return {**base, **{key: str(Decimal(str(base[key])) * factor) for key in RATE_KEYS}}
