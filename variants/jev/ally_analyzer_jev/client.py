"""Small standard-library client for the official, versioned TypeSafe API."""
import math
import os
import time
import urllib.error
import urllib.request

from ally_analyzer.util import AnalyzerError, canonical, integer, strict_json

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MAX_REQUEST_BYTES = 30000
MAX_RESPONSE_BYTES = 1024 * 1024


class JevError(AnalyzerError):
    def __init__(self, code, message, attempts=0):
        super().__init__(message)
        self.code, self.attempts = code, attempts


def number(value, lo, hi):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and lo <= value <= hi


def validate_response(response, payload):
    def invalid():
        raise JevError("invalid_response", "Jev returned an invalid or incompatible response")
    if not isinstance(response, dict) or response.get("model") != payload["model"]:
        invalid()
    answers = response.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(payload["questions"]):
        invalid()
    clean = {}
    for key, question in payload["questions"].items():
        answer = answers[key]
        typ = question["type"]
        if not isinstance(answer, dict) or answer.get("type") != typ:
            invalid()
        if typ == "noul":
            if not number(answer.get("noul"), 0, 1):
                invalid()
            clean[key] = {"type": typ, "noul": answer["noul"]}
            continue
        probabilities = answer.get("probabilities")
        options = set(question["criteria"]) if typ == "choice" else {str(i) for i in range(len(question["criteria"]))}
        if (not isinstance(probabilities, dict) or set(probabilities) != options or
                not all(number(p, 0, 1) for p in probabilities.values()) or
                abs(sum(probabilities.values()) - 1) > 0.005 or not number(answer.get("confidence"), 0, 1)):
            invalid()
        out = {"type": typ, "probabilities": probabilities, "confidence": answer["confidence"]}
        if typ == "choice":
            if answer.get("choice") not in options or probabilities[answer["choice"]] + 0.001 < max(probabilities.values()):
                invalid()
            out["choice"] = answer["choice"]
        elif typ == "score":
            legend = {str(i): v for i, v in enumerate(question["criteria"])}
            if (answer.get("legend") != legend or not number(answer.get("score"), 0, len(legend) - 1) or
                    abs(answer["score"] - sum(int(k) * v for k, v in probabilities.items())) > 0.02):
                invalid()
            out.update(score=answer["score"], legend=legend)
        else:
            invalid()
        clean[key] = out
    usage = response.get("usage")
    if not isinstance(usage, dict) or not all(integer(usage.get(k)) for k in ("input_tokens", "output_tokens")):
        invalid()
    return {"model": response["model"], "answers": clean,
            "usage": {k: usage[k] for k in ("input_tokens", "output_tokens")}}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, settings, api_key=None, transport=None, sleep=time.sleep):
        self.settings = settings
        self.key = api_key if api_key is not None else os.environ.get("TYPESAFE_API_KEY")
        self.transport, self.sleep = transport or self._http, sleep

    def _http(self, payload):
        req = urllib.request.Request(ENDPOINT, data=canonical(payload).encode("utf-8"),
            headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json",
                     "Accept": "application/json", "User-Agent": "ally-session-analyzer-jev/0.1.0"}, method="POST")
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=self.settings["timeout_seconds"]) as r:
            body = r.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise JevError("invalid_response", "Jev response exceeded the size limit")
        return strict_json(body)

    def evaluate(self, payload):
        if not self.key:
            raise JevError("missing_api_key", "Set TYPESAFE_API_KEY in the launching environment to run Jev")
        if len(canonical(payload).encode("utf-8")) > MAX_REQUEST_BYTES:
            raise JevError("request_too_large", "Prepared Jev request exceeds the byte limit")
        start = time.perf_counter()
        for attempt in range(1, self.settings["max_attempts"] + 1):
            try:
                result = validate_response(self.transport(payload), payload)
                return {"response": result, "attempts": attempt,
                        "elapsed_seconds": round(time.perf_counter() - start, 6)}
            except urllib.error.HTTPError as exc:
                # Never expose provider error bodies; they can echo private input.
                if exc.code in (429, 529, 503) and attempt < self.settings["max_attempts"]:
                    try:
                        delay = float(exc.headers.get("Retry-After", 0.5 * 2 ** (attempt - 1)))
                        if not math.isfinite(delay):
                            delay = 1
                    except (TypeError, ValueError):
                        delay = 1
                    self.sleep(max(0.1, min(delay, 10)))
                    continue
                code = {401: "authentication", 403: "forbidden", 402: "billing", 429: "rate_limit",
                        529: "overloaded", 503: "overloaded"}.get(exc.code, "http_error")
                raise JevError(code, "Jev request failed (HTTP %s); baseline analysis is still available" % exc.code, attempt) from None
            except JevError as exc:
                exc.attempts = attempt
                raise
            except (OSError, ValueError, RecursionError):
                # A timed-out POST may already have been processed; do not repeat it.
                raise JevError("transport_or_json", "Jev connection or JSON response failed; request billing may be unknown", attempt) from None
