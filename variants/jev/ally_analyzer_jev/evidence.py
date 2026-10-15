"""Prepare bounded requests locally. Preparing or previewing never calls Jev."""
import re
from collections import defaultdict, deque

from ally_analyzer.engine import canonical_report
from ally_analyzer.normalize import content_blocks as baseline_blocks
from ally_analyzer.util import canonical, digest, strict_json

from .client import MAX_REQUEST_BYTES
from .config import config
from .questions import NOTICE, PROMPT_VERSION, questions

REDACTIONS = [
    (r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+|basic\s+)?[^\s,;\"']+", r"\1[REDACTED]"),
    (r"(?i)((?:api[_-]?key|password|secret|access[_-]?token)\s*[\"']?\s*[:=]\s*[\"']?)[^\s\"',;}]+", r"\1[REDACTED]"),
    (r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|AKIA[A-Z0-9]{16})\b", "[REDACTED]"),
    (r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]"),
    (r"(?:/Users/|/home/)[^/\s]+", "/[USER]"),
]


def content_blocks(record):
    message = record.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return [{"type": "text", "text": message["content"]}]
    return baseline_blocks(record)


def redact(text, settings):
    for pattern, replacement in REDACTIONS:
        text = re.sub(pattern, replacement, text)
    for pattern in settings["redact_patterns"]:
        text = re.sub(pattern, "[REDACTED]", text)
    return text


def excerpt(record, settings, prompt_only=False):
    pieces = []
    for block in content_blocks(record):
        kind = block.get("type")
        if kind == "text" and isinstance(block.get("text"), str):
            pieces.append(block["text"])
        elif not prompt_only and kind == "tool_use":
            pieces.append("Tool " + str(block.get("name", "unknown")) + ": " + canonical(block.get("input", {})))
        elif not prompt_only and kind == "tool_result":
            value = block.get("content", "")
            if isinstance(value, str):
                pieces.append("Tool result: " + value)
            elif isinstance(value, list):
                pieces.extend(str(b["text"]) for b in value if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str))
        # Thinking, images, attachments, environment and top-level fields are excluded.
    text = redact("\n".join(pieces), settings)
    return {"text": text[:settings["excerpt_chars"]], "truncated": len(text) > settings["excerpt_chars"]}


def event_view(row, settings):
    record = strict_json(row["raw"])
    item = {"event_id": row["id"], "kind": row["kind"], "timestamp": row["timestamp"],
            "session_id": row["session_id"], "agent_id": row["agent_id"],
            "block_types": sorted({str(b.get("type", "unknown")) for b in content_blocks(record)})}
    if settings["content_mode"] == "excerpts":
        item.update(excerpt(record, settings))
    else:
        item["content_withheld"] = True
    return item


def fair_selection(items, limit):
    """Deterministic round robin avoids spending the whole cap on one session."""
    groups = defaultdict(deque)
    for item in sorted(items, key=lambda x: x["id"]):
        groups[item["session_ids"][0] if item["session_ids"] else ""].append(item)
    result = []
    while groups and len(result) < limit:
        for key in sorted(list(groups)):
            if len(result) == limit:
                break
            result.append(groups[key].popleft())
            if not groups[key]:
                del groups[key]
    return result


def sample_ids(ids, n):
    if len(ids) <= n:
        return ids
    return [ids[round(i * (len(ids) - 1) / (n - 1))] for i in range(n)] if n > 1 else ids[:1]


def context_rows(db, dataset_id, evidence, count, is_prompt):
    rows = []
    for eid in sample_ids(evidence, min(count, 4)):
        row = db.execute("SELECT * FROM events WHERE dataset_id=? AND id=?", (dataset_id, eid)).fetchone()
        if row is not None:
            rows.append(row)
    if not rows:
        return []
    anchor = min(rows, key=lambda r: (r["timestamp"] or "", r["id"]))
    retained = [] if is_prompt else rows
    previous = db.execute("SELECT * FROM events WHERE dataset_id=? AND session_id=? AND agent_id=? "
        "AND (COALESCE(timestamp,'') < ? OR (COALESCE(timestamp,'') = ? AND id < ?)) "
        "ORDER BY timestamp DESC,id DESC LIMIT ?",
        (dataset_id, anchor["session_id"], anchor["agent_id"], anchor["timestamp"] or "",
         anchor["timestamp"] or "", anchor["id"], count)).fetchall()
    seen = {r["id"] for r in retained}
    for row in previous:
        if len(retained) >= count:
            break
        if row["id"] not in seen:
            retained.append(row)
            seen.add(row["id"])
    return sorted(retained, key=lambda r: (r["timestamp"] or "", r["id"]))


def prepare(store, analysis_id, settings=None):
    settings = config(settings)
    baseline = canonical_report(store, analysis_id)
    dataset_id = baseline["summary"]["dataset_id"]
    findings = baseline["finding"]
    prompts = []
    with store.connect() as db:
        for row in db.execute("SELECT * FROM events WHERE dataset_id=? AND kind='user' ORDER BY id", (dataset_id,)):
            record = strict_json(row["raw"])
            blocks = content_blocks(record)
            if record.get("isMeta") or any(b.get("type") == "tool_result" for b in blocks):
                continue
            if not any(b.get("type") == "text" and b.get("text") for b in blocks):
                continue
            origin = record.get("origin") if isinstance(record.get("origin"), dict) else {}
            prompts.append({"id": row["id"], "evidence": [row["id"]], "session_ids": [row["session_id"]],
                "sender_origin": "recorded_human" if record.get("turnOrigin") == "human" or origin.get("kind") == "human" else "unknown"})
        selected = [("finding", f) for f in fair_selection(findings, settings["max_findings"])]
        if settings["content_mode"] == "excerpts":
            selected += [("prompt", p) for p in fair_selection(prompts, settings["max_prompts"])]
        requests, skipped = [], []
        for kind, item in selected:
            evidence = item.get("evidence", [])
            rows = context_rows(db, dataset_id, evidence, settings["context_events"], kind == "prompt")
            state = {"notice": NOTICE, "content_mode": settings["content_mode"],
                "context": [event_view(row, settings) for row in rows],
                "context_limit": settings["context_events"], "matched_evidence_count": len(evidence),
                "ordering": "Recorded timestamp order within the sampled context; not proof of causality or trace completeness."}
            if kind == "finding":
                state["finding"] = {k: item[k] for k in ("id", "rule_id", "title", "severity", "detail", "condition", "limitation") if k in item}
            else:
                row = db.execute("SELECT * FROM events WHERE dataset_id=? AND id=?", (dataset_id, item["id"])).fetchone()
                state["target_prompt"] = {**event_view(row, settings), "sender_origin": item["sender_origin"]}
            payload = {"model": settings["model"], "state": state, "questions": questions(kind)}
            # A byte cap bounds even atypical text; every removed context item is recorded.
            removed = 0
            while len(canonical(payload).encode("utf-8")) > MAX_REQUEST_BYTES and state["context"]:
                state["context"].pop(0)
                removed += 1
            state["context_items_removed_for_size"] = removed
            if len(canonical(payload).encode("utf-8")) > MAX_REQUEST_BYTES:
                skipped.append({"kind": kind, "target_id": item["id"], "reason": "request_too_large"})
                continue
            refs = sorted(set(([item["id"]] if kind == "prompt" else []) + [r["event_id"] for r in state["context"]]))
            requests.append({"request_id": digest([PROMPT_VERSION, payload]), "kind": kind, "target_id": item["id"],
                "session_ids": item["session_ids"], "sender_origin": item.get("sender_origin"),
                "evidence": refs, "matched_evidence_count": len(evidence),
                "context_coverage": {"context_events": len(state["context"]),
                    "matched_events_included": len(set(refs) & set(evidence)),
                    "truncated_excerpts": sum(bool(r.get("truncated")) for r in state["context"]) +
                        int(bool(state.get("target_prompt", {}).get("truncated"))),
                    "context_items_removed_for_size": removed}, "payload": payload})
    counts = {kind: sum(r["kind"] == kind for r in requests) for kind in ("finding", "prompt")}
    return {"schema_version": "1", "analysis_id": analysis_id, "dataset_id": dataset_id,
        "baseline_sha256": digest(baseline), "prompt_version": PROMPT_VERSION, "configuration": settings,
        "coverage": {"finding_candidates": len(findings), "finding_selected": counts["finding"],
            "prompt_candidates": len(prompts), "prompt_selected": counts["prompt"],
            "prompt_classification_available": settings["content_mode"] == "excerpts",
            "selection": "Stable round robin across sessions per feature; capped, not a random sample.",
            "skipped": skipped}, "requests": requests}


def preview(plan):
    return {k: v for k, v in plan.items() if k != "requests"} | {
        "request_count": len(plan["requests"]),
        "request_bytes": sum(len(canonical(r["payload"]).encode("utf-8")) for r in plan["requests"]),
        "destination": "https://api.typesafe.ai/v1/systemone",
        "network_requests_made": 0, "note": "Preview only. Live excerpt mode sends bounded, redacted transcript text. Pattern redaction is not a guarantee of anonymization."}
