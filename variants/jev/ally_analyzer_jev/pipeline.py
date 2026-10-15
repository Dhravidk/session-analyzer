import os
import re
import tempfile
import threading
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from ally_analyzer.engine import canonical_report
from ally_analyzer.util import AnalyzerError, canonical, digest, strict_json, utc_now

from . import __version__
from .client import Client, JevError, validate_response
from .evidence import prepare, preview


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".writing-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(canonical(value) + "\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_run(store, run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r"jev_[a-f0-9]{32}", run_id):
        raise AnalyzerError("Invalid Jev run ID")
    path = store.root / "jev" / "runs" / run_id / "result.json"
    if not path.is_file():
        raise AnalyzerError("Unknown or unfinished Jev run")
    return strict_json(path.read_text())


def disposition(answers, settings):
    if "prompt_kind" in answers:
        a = answers["prompt_kind"]
        return "review" if (a["choice"] == "insufficient_evidence" or
            a["confidence"] < settings["min_confidence"] or
            a["probabilities"][a["choice"]] < settings["min_probability"]) else "suggested"
    a, p = answers["evidence_sufficiency"], answers["review_priority"]
    return "suggested" if (a["choice"] == "sufficient" and a["confidence"] >= settings["min_confidence"] and
        a["probabilities"]["sufficient"] >= settings["min_probability"] and
        p["confidence"] >= settings["min_confidence"]) else "review"


def interpret(store, analysis_id, settings=None, use_cache=True, client=None, progress=None):
    start = time.perf_counter()
    plan = prepare(store, analysis_id, settings)
    settings = plan["configuration"]
    run_id = "jev_" + uuid.uuid4().hex
    directory = store.root / "jev" / "runs" / run_id
    save_json(directory / "plan.json", plan)
    client = client or Client(settings)
    stop = threading.Event()
    progress_lock, completed = threading.Lock(), 0

    def work(request):
        nonlocal completed
        item = {k: v for k, v in request.items() if k != "payload"}
        item.update(evidence_class="model_interpretation", status="not_attempted", attempts=0,
                    elapsed_seconds=0, cache_hit=False)
        cache = store.root / "jev" / "cache" / (request["request_id"] + ".json")
        response = None
        try:
            if use_cache and cache.is_file():
                try:
                    response = validate_response(strict_json(cache.read_text()), request["payload"])
                    item["cache_hit"] = True
                except (OSError, ValueError, JevError):
                    response = None
            if response is None:
                if stop.is_set():
                    item["error"] = {"code": "stopped_after_account_error", "message": "Not sent after an account or billing error"}
                    return item
                try:
                    result = client.evaluate(request["payload"])
                    # Validate injected clients too; test transports cannot bypass the contract.
                    response = validate_response(result["response"], request["payload"])
                    item.update(attempts=result["attempts"], elapsed_seconds=result["elapsed_seconds"])
                    save_json(cache, response)
                except JevError as exc:
                    item.update(status="failed", attempts=exc.attempts,
                                error={"code": exc.code, "message": str(exc)})
                    if exc.code in ("missing_api_key", "authentication", "forbidden", "billing"):
                        stop.set()
                    return item
            item.update(status="complete", model=response["model"], answers=response["answers"],
                source_usage=response["usage"],
                billed_usage_this_run={"input_tokens": 0, "output_tokens": 0} if item["cache_hit"] else response["usage"],
                disposition=disposition(response["answers"], settings))
            return item
        finally:
            if progress:
                with progress_lock:
                    completed += 1
                    progress({"stage": "jev_interpretation", "requests_done": completed, "requests_total": len(plan["requests"])})

    with ThreadPoolExecutor(max_workers=settings["workers"]) as pool:
        results = list(pool.map(work, plan["requests"]))
    if digest(canonical_report(store, analysis_id)) != plan["baseline_sha256"]:
        raise AnalyzerError("Baseline changed during interpretation; this run cannot be used for A/B comparison")
    counts = Counter(r["status"] for r in results)
    status = "no_candidates" if not results else "complete" if counts["complete"] == len(results) else "partial" if counts["complete"] else "unavailable"
    usage = {k: sum(r.get("billed_usage_this_run", {}).get(k, 0) for r in results) for k in ("input_tokens", "output_tokens")}
    rate = Decimal("0.042") if settings["model"] == "jev-1.13.0" else None
    result = {"schema_version": "1", "variant": "jev", "extension_version": __version__,
        "run_id": run_id, "created_at": utc_now(), "status": status,
        **{k: v for k, v in plan.items() if k != "requests"},
        "operational": {"elapsed_seconds": round(time.perf_counter() - start, 6),
            "prepared_requests": len(results), "completed_requests": counts["complete"],
            "failed_requests": counts["failed"], "not_attempted_requests": counts["not_attempted"],
            "cache_hits": sum(r["cache_hit"] for r in results),
            "http_attempts": sum(r["attempts"] for r in results),
            "usage_from_successful_requests": usage,
            "estimated_successful_request_cost_usd": str(Decimal(usage["input_tokens"]) * rate / 1000000) if rate is not None else None,
            "pricing": {"input_usd_per_million": str(rate) if rate is not None else None,
                        "output_usd_per_million": "0" if rate is not None else None,
                        "checked_date": "2026-10-13", "source": "https://docs.typesafe.ai/models"},
            "failed_attempt_cost_unknown": any(r["attempts"] > 0 and r["status"] != "complete" for r in results),
            "note": "Wall time includes preparation and cache access. Usage covers successful uncached responses only; failed/retried requests may add unreported charges. This is not a vendor invoice or a speedup over baseline."},
        "annotations": results,
        "limitations": ["Model interpretations do not alter canonical counts, rule severities, findings, or coverage.",
            "Confidence summarizes the returned distribution; it is not a validated accuracy rate on Ally logs.",
            "Prompt labels describe message content, not proof of human authorship.",
            "Capped context and sampled targets may omit relevant evidence; all baseline findings remain available."]}
    save_json(directory / "result.json", result)
    return result


def run_summary(run):
    return {k: v for k, v in run.items() if k != "annotations"}
