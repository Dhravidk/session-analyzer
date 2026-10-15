"""Adapter for observed native Claude Code 2.1 transcript records."""
import re
from collections import Counter

from .util import canonical, digest, integer, timestamp

ADAPTER_VERSION = "native-2.1-observed-v4"
OBSERVED_VERSIONS = {"2.1." + str(n) for n in
                     (190, 263, 266, 267, 268, 269, 270, 271, 273, 274, 278,
                      283, 284, 285, 286, 289, 290, 292, 293, 294)}
TOKEN_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
KNOWN_TYPES = {"user", "assistant", "attachment", "system", "cost-state", "mode", "permission-mode",
               "file-history-snapshot", "file-history-delta", "bridge-session", "atis-latch",
               "last-prompt", "ai-title", "queue-operation", "relocated", "summary", "progress", "custom-title", "agent-name"}


def content_blocks(record):
    message = record.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), list):
        return [b for b in message["content"] if isinstance(b, dict)]
    return []


def response_key(record, session, agent, eid):
    m = record.get("message", {})
    mid = m.get("id")
    request = record.get("requestId")
    if quota_notice(record):
        return digest([session, agent, "quota_notice", eid])
    # Provider identities allow copied history to remain one batch response.
    return digest(["provider", request, mid]) if isinstance(request, str) and isinstance(mid, str) else digest([session, agent, mid or eid])


def quota_notice(record):
    # Observed in the supplied Ally 2.1.190 export: a reused sentinel ID,
    # explicit zero usage and ACU quota text, with an ordinary model name.
    # Restrict this exclusion to that exact evidence shape.
    m = record.get("message")
    if not isinstance(m, dict) or m.get("id") != "msg_token_limit" or record.get("requestId"):
        return False
    u = m.get("usage")
    return (record.get("version") == "2.1.190" and isinstance(u, dict)
            and all(integer(u.get(k)) and u[k] == 0 for k in TOKEN_FIELDS)
            and any(b.get("type") == "text" and isinstance(b.get("text"), str)
                    and b["text"].startswith("You've used ") and " ACUs of your " in b["text"]
                    for b in content_blocks(record)))


def reconcile_response(group):
    frames = group.pop("frames")
    frames.sort(key=lambda x: (x["block"] if integer(x["block"]) else -1, x["timestamp"] or "", x["event"]))
    conflicts = ["Conflicting source event identity"] if group.pop("identity_conflict") else []
    aborted = group.pop("aborted")
    if len(group["models"]) > 1:
        conflicts.append("Conflicting models for one response identity")
    by_block = {}
    for f in frames:
        if integer(f["block"]):
            signatures = by_block.setdefault(f["block"], set())
            signatures.add(canonical([f["usage"], f["content_hash"]]))
    if any(len(v) > 1 for v in by_block.values()):
        conflicts.append("Conflicting content or usage for one content-block index")
    usable = [f for f in frames if isinstance(f["usage"], dict)]
    usages = {canonical(f["usage"]) for f in usable}
    status = "missing"
    usage = {}
    if usable:
        usage = usable[-1]["usage"]
        status = "reported_latest_available"
    if len(usages) > 1:
        inputs = [{canonical(f["usage"].get(k)) for f in usable if f["usage"].get(k) is not None}
                  for k in TOKEN_FIELDS[:3]]
        output = [f["usage"].get("output_tokens") for f in usable]
        if (all(f["version"] in OBSERVED_VERSIONS for f in usable)
                and all(len(v) <= 1 for v in inputs)
                and all(integer(v) for v in output) and output == sorted(output)
                and all(integer(f["block"]) for f in usable)):
            status = "reconciled_stream_update"
        else:
            conflicts.append("Usage changed without a supported finalization pattern")
    if conflicts:
        status, usage = "conflict", {}
    elif aborted:
        status, usage = "provisional_interrupted", {}
    tokens = {k: usage.get(k) if integer(usage.get(k)) else None for k in TOKEN_FIELDS}
    details = usage.get("output_tokens_details") or {}
    thinking = details.get("thinking_tokens") if isinstance(details, dict) else None
    tokens["thinking_tokens"] = thinking if integer(thinking) else None
    if integer(thinking) and integer(tokens["output_tokens"]) and thinking > tokens["output_tokens"]:
        tokens["thinking_tokens"] = None
        conflicts.append("Thinking count exceeds inclusive output count")
    tokens["total_input_tokens"] = sum(tokens[k] for k in TOKEN_FIELDS[:3]) if all(tokens[k] is not None for k in TOKEN_FIELDS[:3]) else None
    group.update({"tokens": tokens, "usage_status": status, "warnings": conflicts,
                  "cache_creation": usage.get("cache_creation"), "speed": usage.get("speed"),
                  "service_tier": usage.get("service_tier"), "session_ids": sorted(group["session_ids"]),
                  "agent_ids": sorted(group["agent_ids"]), "models": sorted(group["models"]),
                  "versions": sorted(group["versions"]), "evidence": sorted(group["evidence"]),
                  "shared_history": len(group["session_ids"]) > 1,
                  "scopes": sorted(group["scopes"]),
                  "block_types": dict(sorted(group["block_types"].items()))})
    group["eligible"] = not group["synthetic"]
    return group


def tool_category(name, args):
    if name in ("Read", "Glob", "Grep", "ToolSearch", "WebFetch", "WebSearch"):
        return "discovery"
    if name in ("Write", "Edit", "MultiEdit"):
        return "edit"
    if name in ("Agent", "Task", "TaskStop", "SendMessage"):
        return "coordination"
    if name == "Monitor":
        return "monitoring"
    if name in ("Bash", "PowerShell"):
        command = str(args.get("command", ""))
        if re.search(r"\b(pytest|unittest|npm test|pnpm test|cargo test|go test|jest|vitest)\b", command):
            return "verification"
        if re.search(r"\b(pgrep|tail|nvidia-smi)\b", command) and not re.search(r"\b(rm|kill|tee)\b|>{1,2}", command):
            return "monitoring"
        return "execution"
    if name.startswith("mcp__"):
        return "external_tool"
    if name == "Skill":
        return "skill"
    return "other"


def result_summary(block, record):
    content = block.get("content")
    rendered = content if isinstance(content, str) else canonical(content)
    meta = record.get("toolUseResult")
    meta = meta if isinstance(meta, dict) else {}
    exit_match = re.match(r"^Exit code (\d+)\b", rendered)
    exit_code = int(exit_match.group(1)) if exit_match else None
    outcome, basis = "unknown", "No recognized outcome evidence"
    denial = record.get("toolDenialKind")
    if record.get("version") in OBSERVED_VERSIONS and rendered.startswith("The user doesn't want to proceed with this tool use. The tool use was rejected"):
        outcome, basis = "user_rejection", "Observed native explicit user-rejection result"
    elif denial or rendered.startswith("Permission for this action was denied") or rendered.startswith("<tool_use_error>Blocked:"):
        outcome, basis = ("user_rejection" if denial == "user-rejected" else "permission_denial"), "Explicit denial evidence"
    elif meta.get("interrupted") is True or rendered.startswith("[Request interrupted by user"):
        outcome, basis = "interrupted", "Explicit interruption evidence"
    elif meta.get("timedOutAfterMs") is not None:
        outcome, basis = "timeout", "Recorded timeout field"
    elif record.get("version") in OBSERVED_VERSIONS and rendered.startswith("<tool_use_error>"):
        outcome, basis = "tool_validation_failure", "Native tool-use validation error; execution is not established"
    elif block.get("is_error") is True or meta.get("success") is False or (exit_code is not None and exit_code != 0):
        outcome, basis = "execution_failure", "Reported error or nonzero exit"
    elif block.get("is_error") is False or meta.get("success") is True:
        outcome, basis = "success", "Explicit success or non-error result"
    elif record.get("version") in OBSERVED_VERSIONS and "is_error" not in block:
        outcome, basis = "success", "Native tool_result omitted is_error default; not proof of task success"
    duration = meta.get("durationMs")
    result = {"outcome": outcome, "outcome_basis": basis, "reported_error": block.get("is_error") is True,
              "result_fingerprint": digest(content), "result_bytes": len(rendered.encode("utf-8")),
              "error_signature": digest([outcome, exit_code, rendered]) if outcome != "success" else None,
              "exit_code": exit_code, "recorded_duration_ms": duration if integer(duration) else None,
              "duration_source": "toolUseResult.durationMs" if integer(duration) else None}
    if isinstance(meta.get("agentId"), str):
        result["child_agent_id"] = meta["agentId"]
        result["delegation_status"] = meta.get("status") if isinstance(meta.get("status"), str) else None
        result["child_summary"] = {k: meta[k] for k in ("totalDurationMs", "totalTokens", "totalToolUseCount") if integer(meta.get(k))}
        result["child_summary_additive"] = False
    return result


def finalize_tool(tool):
    calls = tool.pop("calls")
    results = tool.pop("results")
    tool["session_ids"] = sorted(tool["session_ids"])
    tool["agent_ids"] = sorted(tool["agent_ids"])
    tool["scopes"] = sorted(tool["scopes"])
    tool["evidence"] = sorted(tool["evidence"])
    tool["requested"] = bool(calls)
    tool["result_present"] = bool(results)
    tool["warnings"] = ["Conflicting source event identity"] if tool.pop("identity_conflict") else []
    if not calls:
        tool.update({"name": "unknown", "category": "other", "input_fingerprint": None,
                     "timestamp": None, "step_id": None, "inverse_edit": None})
    else:
        tool.update(sorted(calls, key=lambda c: (c["timestamp"] or "", c["evidence_id"]))[0])
    if len({canonical([c["name"], c["input_fingerprint"]]) for c in calls}) > 1:
        tool["warnings"].append("Conflicting arguments for one tool-use ID")
    if len({c["step_id"] for c in calls if c["step_id"]}) > 1:
        tool["warnings"].append("One tool-use ID belongs to multiple response identities")
    signatures = {canonical({k: v for k, v in r.items() if k not in ("timestamp", "event_id")}) for r in results}
    if len(signatures) > 1:
        tool["warnings"].append("Conflicting results for one tool-use ID")
    if results:
        r = sorted(results, key=lambda x: (x["timestamp"] or "", x["event_id"]))[-1]
        tool.update({k: v for k, v in r.items() if k not in ("timestamp", "event_id")})
        tool["result_timestamp"] = r["timestamp"]
    else:
        tool.update({"outcome": "unresolved", "outcome_basis": "No result in imported evidence",
                     "result_timestamp": None, "reported_error": False, "recorded_duration_ms": None,
                     "duration_source": None, "result_bytes": None, "result_fingerprint": None,
                     "error_signature": None, "exit_code": None})
    if tool["warnings"]:
        tool["outcome"] = "conflict"
    elif tool["name"] in ("Agent", "Task") and tool.get("delegation_status") == "async_launched" and tool["outcome"] == "success":
        tool["outcome"] = "launched"
        tool["outcome_basis"] = "Background agent launch acknowledged; completion is not established by this result"
    elif tool["outcome"] == "execution_failure" and tool["category"] == "verification":
        tool["outcome"] = "verification_command_failure"
        tool["outcome_basis"] += "; command resembles a test invocation; failure cause unverified"
    start, end = timestamp(tool.get("timestamp")), timestamp(tool.get("result_timestamp"))
    tool["observed_interval_ms"] = round((end - start) * 1000) if start is not None and end is not None and end >= start else None
    tool["execution_evidence"] = tool["outcome"] in ("success", "launched", "execution_failure", "verification_command_failure", "timeout")
    return tool


def parse_events(rows, progress=None):
    responses, tools, sessions, lifecycle = {}, {}, {}, []
    kinds, versions, attachments = Counter(), Counter(), Counter()
    for i, row in enumerate(rows):
        r, eid, sid, aid = row["record"], row["id"], row["session_id"], row["agent_id"]
        typ, ts, version = r["type"], row["timestamp"], row["version"]
        kinds[typ] += 1
        if version:
            versions[version] += 1
        s = sessions.setdefault(sid, {"id": sid, "session_ids": [sid], "events": 0, "agents": set(), "versions": set(),
                                      "first_timestamp": None, "last_timestamp": None, "human_prompts": 0,
                                      "other_prompt_origins": Counter(), "recorded_turn_durations_ms": [], "evidence": []})
        s["events"] += 1
        s["agents"].add(aid)
        if version:
            s["versions"].add(version)
        if timestamp(ts) is not None:
            s["first_timestamp"] = min(s["first_timestamp"] or ts, ts)
            s["last_timestamp"] = max(s["last_timestamp"] or ts, ts)
        blocks = content_blocks(r)
        step_id = None
        if typ == "assistant" and isinstance(r.get("message"), dict):
            m = r["message"]
            key = response_key(r, sid, aid, eid)
            step_id = "response_" + key[:24]
            g = responses.setdefault(key, {"id": step_id, "message_id": m.get("id"), "request_id": r.get("requestId"),
                "session_ids": set(), "agent_ids": set(), "scopes": set(), "models": set(), "versions": set(), "frames": [],
                "evidence": set(), "block_types": Counter(), "timestamp": ts,
                "synthetic": m.get("model") == "<synthetic>" or quota_notice(r),
                "synthetic_basis": "observed_quota_notice" if quota_notice(r) else ("explicit_synthetic_model" if m.get("model") == "<synthetic>" else None),
                "aborted": False, "identity_conflict": False})
            g["session_ids"].add(sid)
            g["agent_ids"].add(aid)
            g["scopes"].add((sid, aid))
            g["models"].add(str(m.get("model") or "unknown"))
            if version:
                g["versions"].add(version)
            g["evidence"].add(eid)
            g["block_types"].update(str(b.get("type", "unknown")) for b in blocks)
            g["aborted"] = g["aborted"] or r.get("isAbortedMidStream") is True
            g["identity_conflict"] = g["identity_conflict"] or row.get("identity_conflict", False)
            g["frames"].append({"usage": m.get("usage"), "block": r.get("apiBlockIndex"), "timestamp": ts,
                                "event": eid, "version": version, "content_hash": digest(m.get("content"))})
            if ts and (not g["timestamp"] or ts < g["timestamp"]):
                g["timestamp"] = ts
        if typ == "user" and not any(b.get("type") == "tool_result" for b in blocks):
            origin = r.get("origin") if isinstance(r.get("origin"), dict) else {}
            if r.get("turnOrigin") == "human" or origin.get("kind") == "human":
                s["human_prompts"] += 1
            else:
                s["other_prompt_origins"][str(r.get("turnOrigin") or r.get("promptSource") or "unknown")] += 1
        for b in blocks:
            bt = b.get("type")
            tid = b.get("id") if bt == "tool_use" else b.get("tool_use_id")
            if bt not in ("tool_use", "tool_result") or not isinstance(tid, str):
                continue
            t = tools.setdefault(tid, {"id": tid, "session_ids": set(), "agent_ids": set(), "scopes": set(), "evidence": set(), "calls": [], "results": [], "identity_conflict": False})
            t["session_ids"].add(sid)
            t["agent_ids"].add(aid)
            t["scopes"].add((sid, aid))
            t["evidence"].add(eid)
            t["identity_conflict"] = t["identity_conflict"] or row.get("identity_conflict", False)
            if bt == "tool_use":
                args = b.get("input") if isinstance(b.get("input"), dict) else {}
                name = str(b.get("name") or "unknown")
                # Description is display-only; preserve every executable command byte.
                match_args = {k: v for k, v in args.items() if not (name in ("Bash", "PowerShell", "Monitor") and k == "description")}
                inverse = None
                if name == "Edit" and all(isinstance(args.get(k), str) for k in ("file_path", "old_string", "new_string")):
                    inverse = {"file_hash": digest(args["file_path"]), "old_hash": digest(args["old_string"]),
                               "new_hash": digest(args["new_string"]), "replace_all": args.get("replace_all", False)}
                t["calls"].append({"name": name, "category": tool_category(name, args), "input_fingerprint": digest(match_args),
                    "timestamp": ts, "step_id": step_id, "evidence_id": eid, "inverse_edit": inverse})
            else:
                t["results"].append(dict(result_summary(b, r), timestamp=ts, event_id=eid))
        if typ == "attachment" and isinstance(r.get("attachment"), dict):
            attachments[str(r["attachment"].get("type") or "unknown")] += 1
        if typ in ("system", "cost-state", "permission-mode", "relocated", "file-history-delta"):
            event = {"id": eid, "session_ids": [sid], "agent_id": aid, "kind": typ,
                     "subtype": str(r.get("subtype") or typ), "timestamp": ts, "evidence": [eid]}
            if typ == "system" and r.get("subtype") == "turn_duration" and integer(r.get("durationMs")):
                event["recorded_duration_ms"] = r["durationMs"]
                s["recorded_turn_durations_ms"].append(r["durationMs"])
            if r.get("subtype") == "compact_boundary":
                md = r.get("compactMetadata") if isinstance(r.get("compactMetadata"), dict) else {}
                event["compaction"] = {k: md.get(k) for k in ("trigger", "preTokens", "postTokens", "durationMs")}
            if typ == "cost-state":
                # Snapshots are preserved as estimates; never added to response usage.
                event["recorded_cost_estimate_usd"] = r.get("totalCostUSD")
                event["process_start_time"] = r.get("startTime")
                event["models"] = sorted(r["modelUsage"]) if isinstance(r.get("modelUsage"), dict) else []
            lifecycle.append(event)
        if progress and i % 1000 == 0:
            progress({"stage": "normalize", "events_done": i})
    for s in sessions.values():
        s["agents"], s["versions"] = sorted(s["agents"]), sorted(s["versions"])
        s["other_prompt_origins"] = dict(sorted(s["other_prompt_origins"].items()))
        start, end = timestamp(s["first_timestamp"]), timestamp(s["last_timestamp"])
        s["observed_span_ms"] = round((end - start) * 1000) if start is not None and end is not None else None
        del s["evidence"]
    return {"responses": sorted((reconcile_response(g) for g in responses.values()), key=lambda x: x["id"]),
            "tools": sorted((finalize_tool(t) for t in tools.values()), key=lambda x: x["id"]),
            "sessions": sorted(sessions.values(), key=lambda x: x["id"]), "lifecycle": lifecycle,
            "record_types": dict(sorted(kinds.items())), "version_counts": dict(sorted(versions.items())),
            "attachment_types": dict(sorted(attachments.items()))}
