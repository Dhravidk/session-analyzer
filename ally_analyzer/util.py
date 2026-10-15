import hashlib
import json
import math
from datetime import datetime, timezone


class AnalyzerError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def strict_json(data):
    def reject(value):
        raise ValueError("Non-finite JSON number: " + value)
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError("Duplicate JSON object key")
            result[k] = v
        return result
    return json.loads(data, parse_constant=reject, object_pairs_hook=pairs)


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.timestamp()
    except (ValueError, OverflowError):
        return None


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def normalized_timestamp(value):
    if timestamp(value) is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat(timespec="microseconds")


def bounded(value, low, high, name):
    if not integer(value) or not low <= value <= high:
        raise AnalyzerError("%s must be an integer between %s and %s" % (name, low, high))
    return value


def percentile(values, p):
    return sorted(values)[max(0, math.ceil(len(values) * p) - 1)] if values else None
