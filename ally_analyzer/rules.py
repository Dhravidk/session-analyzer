from collections import defaultdict

from .util import digest

DEFAULT_PROFILE = {"repeat_min": 3, "repeat_window_steps": 10, "context_input_threshold": 200000,
                   "tool_output_bytes_threshold": 65536, "sequence_max_period": 5}


def validate_profile(profile):
    from .util import AnalyzerError, integer
    if profile is not None and not isinstance(profile, dict):
        raise AnalyzerError("Rule profile must be an object")
    config = dict(DEFAULT_PROFILE)
    for k, v in (profile or {}).items():
        if k not in config or not integer(v) or not 1 <= v <= 10000000:
            raise AnalyzerError("Unknown or invalid profile setting: " + str(k))
        config[k] = v
    if not 2 <= config["repeat_min"] <= 20 or not 2 <= config["sequence_max_period"] <= 8:
        raise AnalyzerError("repeat_min must be 2–20 and sequence_max_period 2–8")
    if config["repeat_window_steps"] > 1000:
        raise AnalyzerError("repeat_window_steps must not exceed 1000")
    return config


def find_patterns(data, profile, diagnostics):
    findings = []
    def add(rule, title, severity, items, detail, condition):
        evidence = sorted({e for x in items for e in x.get("evidence", [])})
        sessions = sorted({s for x in items for s in x.get("session_ids", [])})
        body = {"rule_id": rule, "rule_version": "1", "title": title, "severity": severity,
                "evidence_class": "rule_finding", "session_ids": sessions, "evidence": evidence,
                "detail": detail, "condition": condition,
                "limitation": "Pattern in imported evidence; cause and wasted effort are not established."}
        body["id"] = "finding_" + digest(body)[:24]
        findings.append(body)
    groups = defaultdict(list)
    response_order = sorted(data["responses"], key=lambda x: (x.get("timestamp") or "", x["id"]))
    steps = {r["id"]: i for i, r in enumerate(response_order)}
    # Step distances are local to each agent run, not inflated by concurrent agents.
    local_steps = defaultdict(dict)
    for r in response_order:
        for sid, aid in r["scopes"]:
            local_steps[(sid, aid)][r["id"]] = len(local_steps[(sid, aid)])
    for t in data["tools"]:
        if t["requested"]:
            for sid, aid in t["scopes"]:
                groups[(sid, aid)].append(t)
    for scope, group in sorted(groups.items()):
        group.sort(key=lambda t: (t.get("timestamp") or "", t["id"]))
        buckets = defaultdict(list)
        inverses = {}
        for t in group:
            idx = local_steps[scope].get(t["step_id"], steps.get(t["step_id"], 0))
            sig = (t["name"], t["input_fingerprint"], t["result_fingerprint"], t["outcome"])
            buckets[sig].append((idx, t))
            edit = t.get("inverse_edit")
            if edit and t["outcome"] == "success":
                key = (edit["file_hash"], edit["old_hash"], edit["new_hash"], edit["replace_all"])
                reverse = (key[0], key[2], key[1], key[3])
                if reverse in inverses and key[1] != key[2]:
                    add("R04", "Recorded inverse edits", "notice", [inverses[reverse], t],
                        "An edit reverses the recorded replacement of an earlier edit. Full file state is not established.",
                        {"scope": list(scope), "matching_file_and_replacement_hashes": True})
                inverses[key] = t
        for sig, seq in sorted(buckets.items(), key=lambda kv: str(kv[0])):
            windows, current = [], []
            for idx, t in seq:
                current = [(i, x) for i, x in current if idx - i <= profile["repeat_window_steps"]]
                current.append((idx, t))
                if len(current) >= profile["repeat_min"]:
                    windows.append([x for _, x in current])
            if not windows:
                continue
            matches = {x["id"]: x for w in windows for x in w}
            items = sorted(matches.values(), key=lambda t: t["id"])
            condition = {"scope": list(scope), "matched_calls": len(items), "minimum": profile["repeat_min"],
                         "window_model_steps": profile["repeat_window_steps"]}
            if sig[3] in ("execution_failure", "tool_validation_failure", "verification_command_failure", "timeout", "permission_denial", "user_rejection"):
                add("R01", "Repeated invocation with the same failure", "warning", items,
                    "The same tool arguments and captured failure result recur within the configured step window.", condition)
            elif items[0]["category"] == "monitoring" and sig[3] == "success":
                add("R03", "Repeated status checks with identical results", "notice", items,
                    "Captured results are identical. This can be intentional monitoring.", condition)
        signatures = [(t["name"], t["input_fingerprint"], t["result_fingerprint"], t["outcome"]) for t in group]
        covered = set()
        repeats = profile["repeat_min"]
        for period in range(2, profile["sequence_max_period"] + 1):
            for start in range(0, len(group) - period * repeats + 1):
                end = start + period * repeats
                pattern = signatures[start:start + period]
                if len(set(pattern)) < 2 or any(i in covered for i in range(start, end)):
                    continue
                if signatures[start:end] == pattern * repeats:
                    items = group[start:end]
                    positions = [local_steps[scope].get(t["step_id"], 0) for t in items]
                    if max(positions) - min(positions) > profile["repeat_window_steps"]:
                        continue
                    add("R02", "Repeated tool sequence", "notice", items,
                        "A contiguous sequence of tool arguments and captured results repeats. External state may be unobserved.",
                        {"scope": list(scope), "period": period, "repetitions": repeats})
                    covered.update(range(start, end))
    for sid in (s["id"] for s in data["sessions"]):
        big = [r for r in data["responses"] if sid in r["session_ids"] and
               (r["tokens"].get("total_input_tokens") or 0) > profile["context_input_threshold"]]
        if big:
            add("R05", "Large recorded model input", "notice", big,
                "Recorded input exceeds the analyst's configured threshold. This is not a model context-limit check.",
                {"threshold_tokens": profile["context_input_threshold"], "responses": len(big),
                 "max_input_tokens": max(r["tokens"]["total_input_tokens"] for r in big)})
    for t in data["tools"]:
        if (t.get("result_bytes") or 0) > profile["tool_output_bytes_threshold"]:
            add("R05", "Large captured tool result", "notice", [t],
                "Captured tool content exceeds the configured byte threshold. Byte size is not a token count.",
                {"threshold_bytes": profile["tool_output_bytes_threshold"], "result_bytes": t["result_bytes"]})
        if t.get("child_agent_id") and not t.get("child_trace_available"):
            add("R09", "Delegated agent transcript unavailable", "warning", [t],
                "The parent result names an agent whose transcript is absent. Parent summaries are preserved separately and not added to response totals.",
                {"child_agent_id": t["child_agent_id"], "delegation_status": t.get("delegation_status")})
        if not t["result_present"] or not t["requested"] or t["warnings"]:
            add("R09", "Incomplete or conflicting tool trace", "warning", [t],
                "The invocation has no matching call/result or has conflicting identity evidence.",
                {"requested": t["requested"], "result_present": t["result_present"], "warnings": t["warnings"]})
    for r in data["responses"]:
        if r["eligible"] and r["usage_status"] in ("missing", "conflict", "provisional_interrupted"):
            add("R09", "Model usage needs qualification", "warning", [r],
                "This response is excluded from unavailable token categories; totals report coverage.", {"usage_status": r["usage_status"]})
    # This deliberately requires an exact successful retry of the same arguments.
    # A different repair may exist; the finding never claims the task was unfixed.
    for scope, group in sorted(groups.items()):
        unresolved = []
        for i, t in enumerate(group):
            if t["outcome"] not in ("execution_failure", "tool_validation_failure", "verification_command_failure", "timeout"):
                continue
            recovered = any(x["name"] == t["name"] and x["input_fingerprint"] == t["input_fingerprint"]
                            and x["outcome"] == "success" for x in group[i + 1:])
            if not recovered:
                unresolved.append(t)
        if unresolved:
            add("R06", "Failures without an exact successful retry", "notice", unresolved,
                "No later successful invocation with the same tool and arguments is recorded in this agent run. Recovery through changed commands or outside this trace remains unknown.",
                {"scope": list(scope), "failed_invocations": len(unresolved), "recovery_definition": "exact_arguments_successful_retry"})
    if diagnostics:
        add("R09", "Import diagnostics affect trace coverage", "warning", [],
            "Inspect import diagnostics; unavailable records were not silently repaired.",
            {"diagnostic_ids": sorted(d["id"] for d in diagnostics), "count": len(diagnostics)})
    return sorted({f["id"]: f for f in findings}.values(), key=lambda f: f["id"])
