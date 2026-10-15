import re
from pathlib import Path

from ally_analyzer.util import AnalyzerError, bounded, strict_json

DEFAULTS = {
    "model": "jev-1.13.0", "content_mode": "metadata",
    "max_findings": 200, "max_prompts": 200,
    "context_events": 8, "excerpt_chars": 1400,
    "workers": 4, "timeout_seconds": 30, "max_attempts": 3,
    "min_confidence": 0.6, "min_probability": 0.7,
    "redact_patterns": [],
}
BOUNDS = {"max_findings": (0, 2000), "max_prompts": (0, 2000),
          "context_events": (1, 12), "excerpt_chars": (100, 2000),
          "workers": (1, 8), "timeout_seconds": (1, 60), "max_attempts": (1, 4)}


def config(values=None):
    if values is not None and (not isinstance(values, dict) or set(values) - set(DEFAULTS)):
        raise AnalyzerError("Unknown Jev configuration fields")
    result = {**DEFAULTS, **(values or {})}
    if not isinstance(result["model"], str) or not re.fullmatch(r"jev-\d+\.\d+\.\d+", result["model"]):
        raise AnalyzerError("Pin an exact Jev version, for example jev-1.13.0; moving aliases are excluded from A/B runs")
    if result["content_mode"] not in ("metadata", "excerpts"):
        raise AnalyzerError("content_mode must be metadata or excerpts")
    for name, limits in BOUNDS.items():
        bounded(result[name], *limits, name)
    for name in ("min_confidence", "min_probability"):
        value = result[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise AnalyzerError(name + " must be a number between zero and one")
    patterns = result["redact_patterns"]
    if not isinstance(patterns, list) or len(patterns) > 20:
        raise AnalyzerError("redact_patterns must contain at most 20 regular expressions")
    for pattern in patterns:
        if not isinstance(pattern, str) or not 1 <= len(pattern) <= 500:
            raise AnalyzerError("Invalid redaction pattern")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise AnalyzerError("Invalid redaction regular expression") from exc
    return result


def load_config(path=None):
    return config(strict_json(Path(path).read_text()) if path else None)
