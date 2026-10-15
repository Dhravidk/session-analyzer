"""Descriptive per-turn patterns, never a quality or waste classifier."""
from collections import defaultdict
from statistics import median

PATTERN_VERSION = "turn-patterns-v1"
RECORDED_FAILURE_OUTCOMES = frozenset(("execution_failure", "verification_command_failure", "timeout"))
RULES = [
    ("no_response", "No recorded response", "No eligible model response assigned to this request."),
    ("llm_only", "No tool calls", "Recorded model response(s), with no assigned tool invocation."),
    ("single_batch", "Single tool batch", "Exactly one model response emitted the assigned tool calls."),
    ("edit_check", "Edit and check", "Multiple tool batches with both editing and verification calls."),
    ("read", "Read and search", "Multiple tool batches; every assigned call is reading or search."),
    ("terminal", "Terminal-led", "Multiple tool batches; at least half the assigned calls use a terminal."),
    ("mixed", "Other activity", "Other combinations of assigned tool calls."),
]


def turn_patterns(turns, tools):
    tool_map = {t["id"]: t for t in tools}
    groups = defaultdict(list)
    for turn in turns:
        calls = [tool_map[t] for t in turn["tool_ids"] if tool_map[t]["requested"]]
        batches = {t["step_id"] for t in calls if t.get("step_id")}
        categories = {t["category"] for t in calls}
        llm = turn["metrics"]["llm_calls"]["value"]
        if not llm and not calls:
            key = "no_response"
        elif not calls:
            key = "llm_only"
        elif len(batches) == 1:
            key = "single_batch"
        elif categories & {"edit", "write"} and "verification" in categories:
            key = "edit_check"
        elif categories <= {"discovery"}:
            key = "read"
        elif sum(t["name"] in ("Bash", "PowerShell", "Terminal") for t in calls) * 2 >= len(calls):
            key = "terminal"
        else:
            key = "mixed"
        failed = sum(t["outcome"] in RECORDED_FAILURE_OUTCOMES for t in calls)
        groups[key].append({"turn_id": turn["id"], "llm_calls": llm, "tool_batches": len(batches),
                            "recorded_failures": failed, "unknown_outcomes": sum(t["outcome"] in ("unknown", "unresolved", "conflict") for t in calls)})
    result = []
    for key, label, description in RULES:
        members = groups[key]
        if not members:
            continue
        result.append({"id": key, "archetype": label, "description": description, "turns": len(members),
                       "share": len(members) / len(turns), "median_llm_calls": median(m["llm_calls"] for m in members),
                       "median_tool_batches": median(m["tool_batches"] for m in members),
                       "known_turns": len(members), "eligible_turns": len(members),
                       "turns_with_recorded_failures": sum(m["recorded_failures"] > 0 for m in members),
                       "recorded_failures": sum(m["recorded_failures"] for m in members),
                       "unknown_tool_outcomes": sum(m["unknown_outcomes"] for m in members),
                       "member_turn_ids": [m["turn_id"] for m in members]})
    return {"version": PATTERN_VERSION, "population": "All reconstructed user turns in this session scope, including requests with no recorded response",
            "denominator": len(turns), "rows": result, "rules_in_precedence_order": [dict(id=k, label=l, rule=d) for k, l, d in RULES],
            "batch_definition": "One reconciled response that emitted one or more tool invocations. Not proof of concurrent execution.",
            "failure_definition": "Recorded execution_failure, verification_command_failure or timeout outcomes. Permission denials, user rejections and input validation failures are separate outcome categories. Unknown outcomes remain unknown.",
            "interpretation": "Descriptive grouping only. Failures may be expected. Shares describe observed turns, not time, tokens or cross-session prevalence."}
