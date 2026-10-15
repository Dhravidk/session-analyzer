"""Session and turn measurements with explicit identities, populations and bounds."""
from collections import Counter, defaultdict
import re

from .engine import compute_metrics
from .normalize import content_blocks
from .session_scope import entities, get_scope, scope_rows
from .util import digest, integer, strict_json, timestamp

VERSION = "session-turn-metrics-v3"
DEFINITIONS = {
    "task_requests": "Distinct captured main-agent task requests from explicit human/user origins, explicit SDK submissions, or inferred requests with unspecified origin. Tool results, metadata, summaries and recognized CLI controls are excluded. This population is not proof that all intended requirements were captured.",
    "human_origin_turns": "Task requests explicitly marked human or user by the captured host. This records provenance; it does not independently prove who typed the request. SDK and unspecified origins are excluded.",
    "user_turns": "Distinct captured main-agent user requests. Tool results, explicit non-human origins, metadata, compaction summaries and recognized local CLI control records are excluded. Unspecified origin is marked inferred; the log cannot prove a human typed it.",
    "llm_calls": "Eligible reconciled model responses, including responses with unavailable usage. This is an observed-call proxy; transport attempts and retries remain unavailable.",
    "tool_invocations": "Distinct requested tool-use IDs, including calls that were denied. Not a count of executed commands.",
    "session_duration_minutes": "First to last valid timestamp in the admitted root/child scope. Includes idle intervals and concurrency; not active work or avoidable overhead.",
    "prompt_tokens": "Input + cache-creation input + cache-read input, once per eligible response with all components known. Cached tokens are already included.",
    "cached_tokens": "Cache-read input tokens. Cache creation is reported separately; never add cached tokens again to prompt tokens.",
    "cache_creation_tokens": "Cache-creation input tokens, already included in prompt tokens.",
    "uncached_input_tokens": "Reported input tokens excluding cache reads and cache creation.",
    "completion_tokens": "Inclusive output tokens; reported thinking is already included.",
    "turn_duration_seconds": "Explicit system turn_duration durationMs linked to the request, when exactly one unambiguous duration record exists. Otherwise unknown. Observed turn span is separate.",
    "observed_turn_span_seconds": "Request timestamp to last attributed event, not time to the next user message and not proven completion latency.",
}


def metric(name, value, unit, known, eligible, source_ids, **extra):
    return {"definition_id": name + ":" + VERSION, "definition": DEFINITIONS.get(name, name), "value": value,
            "unit": unit, "known": known, "eligible": eligible, "known_subtotal": extra.pop("known_subtotal", value),
            "complete_for_observed_population": known == eligible, "source_ids": sorted(set(source_ids)), **extra}


def request_origin(row, include_sdk=False):
    r = row["record"]
    if row["agent_id"] != "main" or r.get("type") != "user":
        return None
    if any(b.get("type") == "tool_result" for b in content_blocks(r)):
        return None
    if r.get("isMeta") or r.get("isCompactSummary"):
        return None
    origin = r.get("origin") if isinstance(r.get("origin"), dict) else {}
    supplied = r.get("turnOrigin") or origin.get("kind") or r.get("promptSource")
    if supplied and supplied not in (("human", "user", "sdk") if include_sdk else ("human", "user")):
        return None
    content = (r.get("message") or {}).get("content")
    if not content:
        return None
    visible = content if isinstance(content, str) else '\n'.join(b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text')
    # These exact native control shapes occur as user-role records without
    # human provenance. Do not turn CLI output or interruption notices into
    # conversational turns. Unknown commands remain inferred, not discarded.
    if not supplied:
        if visible.strip() in ('[Request interrupted by user]', '[Request interrupted by user for tool use]'):
            return None
        if visible.lstrip().startswith(('<local-command-stdout>', '<local-command-stderr>', '<local-command-caveat>')):
            return None
        if re.search(r'<command-name>/(?:model|plugin|exit)</command-name>', visible):
            return None
    if supplied == 'sdk': return 'explicit_sdk_request'
    return "explicit_human" if supplied in ("human", "user") else "inferred_user_request_unknown_origin"


def token_metrics(responses):
    eligible = [r for r in responses if r["eligible"]]
    result = {}
    fields = {"prompt_tokens": "total_input_tokens", "cached_tokens": "cache_read_input_tokens",
              "completion_tokens": "output_tokens", "uncached_input_tokens": "input_tokens",
              "cache_creation_tokens": "cache_creation_input_tokens"}
    for name, field in fields.items():
        known = [r for r in eligible if r["tokens"].get(field) is not None]
        subtotal = sum(r["tokens"][field] for r in known)
        result[name] = metric(name, subtotal if len(known) == len(eligible) else None, "tokens", len(known), len(eligible),
                              [eid for r in known for eid in r["evidence"]], known_subtotal=subtotal,
                              unavailable_reason="Some response usage is unavailable" if len(known) < len(eligible) else None)
    return result


def turn_accounting(store, run):
    rows = scope_rows(store, run)
    for row in rows:
        row["record"] = strict_json(row["raw"])
    by_id = {r["id"]: r for r in rows}
    by_uuid = defaultdict(list)
    for row in rows:
        if row["record"].get("uuid"):
            by_uuid[row["record"]["uuid"]].append(row["id"])
    requests = {r["id"]: request_origin(r, include_sdk=True) for r in rows if request_origin(r, include_sdk=True)}
    attribution, basis = {}, {}
    # Resolve recorded ancestry first; fallback is explicitly labelled and only
    # applies to main-agent records without a recorded parent link.
    current = None
    for row in rows:
        eid, raw = row["id"], row["record"]
        if eid in requests:
            attribution[eid] = eid; basis[eid] = "request_identity"; current = eid
            continue
        seen, cursor, owner = set(), eid, None
        while cursor not in seen:
            seen.add(cursor)
            if cursor in requests:
                owner = cursor; break
            parent = by_id[cursor]["record"].get("parentUuid")
            candidates = by_uuid.get(parent, [])
            if len(candidates) != 1:
                break
            cursor = candidates[0]
        if owner:
            attribution[eid] = owner; basis[eid] = "recorded_parent_ancestry"
        elif row["agent_id"] == "main" and not raw.get("parentUuid") and current and row["timestamp"]:
            attribution[eid] = current; basis[eid] = "inferred_main_agent_order"
    responses, tools = entities(store, run, "response"), entities(store, run, "tool")
    # Children belong to their recorded delegation, not to the nearest later
    # timestamp. Shared/multiple-parent delegation is deliberately unassigned.
    links = get_scope(store, run)["delegation_links"]
    tool_map = {t["id"]: t for t in tools}
    for _ in range(len(links) + 1):
        changed = False
        for agent in sorted({r["agent_id"] for r in rows} - {"main"}):
            parent_calls = {x["tool_id"] for x in links if x["child_agent_id"] == agent}
            owners = {attribution.get(tool_map[t].get("evidence_id")) for t in parent_calls if t in tool_map}
            if len(owners) == 1 and None not in owners:
                owner = next(iter(owners))
                for row in rows:
                    if row["agent_id"] == agent and row["id"] not in attribution:
                        attribution[row["id"]] = owner; basis[row["id"]] = "recorded_delegation"; changed = True
        if not changed:
            break
    response_owner = {}
    for response in responses:
        owners = {attribution.get(eid) for eid in response["evidence"]}
        if len(owners) == 1 and None not in owners:
            response_owner[response["id"]] = next(iter(owners))
    tool_owner = {t["id"]: response_owner[t["step_id"]] for t in tools if t.get("step_id") in response_owner}
    turns = []
    for request, origin in requests.items():
        member_rows = [r for r in rows if attribution.get(r["id"]) == request]
        rs = [r for r in responses if response_owner.get(r["id"]) == request]
        ts = [t for t in tools if tool_owner.get(t["id"]) == request]
        metrics = token_metrics(rs)
        eligible = [r for r in rs if r["eligible"]]
        metrics["llm_calls"] = metric("llm_calls", len(eligible), "count", len(eligible), len(eligible), [e for r in eligible for e in r["evidence"]])
        requested = [t for t in ts if t["requested"]]
        metrics["tool_invocations"] = metric("tool_invocations", len(requested), "count", len(requested), len(requested), [e for t in requested for e in t["evidence"]])
        durations = [r for r in member_rows if r["agent_id"] == "main" and r["record"].get("subtype") == "turn_duration"]
        known_duration = len(durations) == 1 and integer(durations[0]["record"].get("durationMs"))
        metrics["turn_duration_seconds"] = metric("turn_duration_seconds", durations[0]["record"]["durationMs"] / 1000 if known_duration else None,
                   "seconds", int(known_duration), 1, [r["id"] for r in durations],
                   unavailable_reason=None if known_duration else "Missing, invalid or multiple turn-duration records",
                   attribution_basis=basis.get(durations[0]["id"]) if known_duration else None)
        start = timestamp(by_id[request]["timestamp"])
        times = [(timestamp(r["timestamp"]), r["id"]) for r in member_rows if timestamp(r["timestamp"]) is not None]
        end = max(times) if times else None
        span = end[0] - start if end and start is not None and end[0] >= start else None
        metrics["observed_turn_span_seconds"] = metric("observed_turn_span_seconds", span, "seconds", len(times), len(member_rows),
                                                       [request, end[1]] if end else [request])
        turns.append({"id": "turn_" + digest([run["scope_id"], request])[:24], "request_event_id": request,
                      "origin_basis": origin, "response_ids": sorted(r["id"] for r in rs), "tool_ids": sorted(t["id"] for t in ts),
                      "event_ids": [r["id"] for r in member_rows], "attribution_bases": dict(Counter(basis[r["id"]] for r in member_rows)), "metrics": metrics})
    return turns, {"responses_without_unambiguous_turn": sorted(r["id"] for r in responses if r["eligible"] and r["id"] not in response_owner),
                   "tools_without_unambiguous_turn": sorted(t["id"] for t in tools if t["requested"] and t["id"] not in tool_owner),
                   "events_without_turn": len(rows) - len(attribution), "turn_attribution_is_not_causality": True}


def session_accounting(store, run):
    rows = scope_rows(store, run)
    responses, tools = entities(store, run, "response"), entities(store, run, "tool")
    turns, coverage = turn_accounting(store, run)
    metrics = token_metrics(responses)
    human = [t for t in turns if t['origin_basis'] == 'explicit_human']
    inferred = [t for t in turns if t['origin_basis'] == 'inferred_user_request_unknown_origin']
    for name, population in (('task_requests',turns), ('human_origin_turns',human), ('user_turns',human+inferred)):
        metrics[name] = metric(name,len(population),'count',len(population),len(population),[t['request_event_id'] for t in population],
                              complete_for_observed_population=bool(population),
                              population_status='observed' if population else 'empty_population')
    metrics['task_requests'].update(origin_counts=dict(Counter(t['origin_basis'] for t in turns)))
    metrics['user_turns'].update(explicit_human_count=len(human), inferred_origin_count=len(inferred))
    eligible = [r for r in responses if r["eligible"]]
    requested = [t for t in tools if t["requested"]]
    metrics["llm_calls"] = metric("llm_calls", len(eligible), "count", len(eligible), len(eligible), [e for r in eligible for e in r["evidence"]])
    metrics["tool_invocations"] = metric("tool_invocations", len(requested), "count", len(requested), len(requested), [e for t in requested for e in t["evidence"]])
    times = [(timestamp(r["timestamp"]), r["id"]) for r in rows if timestamp(r["timestamp"]) is not None]
    start, end = min(times) if times else None, max(times) if times else None
    metrics["session_duration_minutes"] = metric("session_duration_minutes", (end[0] - start[0]) / 60 if start and len(times) >= 2 else None,
                 "minutes", len(times), len(rows), [start[1], end[1]] if start else [], interval_basis="observed retained endpoints")
    return {"version": VERSION, "session": metrics, "turns": turns, "attribution_coverage": coverage,
            "source_session_usage_only": True, "api_attempts": None, "api_retries": None,
            "limitations": "Observed records only. Missing usage is unknown, not zero. Child rollup summaries are not added. Intervals include idle time and concurrent work."}
