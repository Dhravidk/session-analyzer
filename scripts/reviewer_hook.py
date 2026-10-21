#!/usr/bin/env python3
"""Claude host hooks: persist reviewer identity and deny duplicate paid launches."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ally_analyzer.native_review import hook_event
from ally_analyzer.store import Store


def main():
    payload = {}
    try:
        value = json.load(sys.stdin)
        if not isinstance(value, dict):
            raise ValueError('Expected a host hook object')
        payload = value
        if ('--analysis-only' in sys.argv and payload.get('hook_event_name') == 'PreToolUse'
                and payload.get('tool_name') == 'Agent'
                and (payload.get('tool_input') or {}).get('subagent_type') != 'ally-session-analyzer:source-review'
                and not (payload.get('tool_input') or {}).get('resume')):
            raise ValueError('During /analyze, only the saved source-review Agent may be launched. Use scoped MCP readers; do not launch helper agents for spill files')
        result = hook_event(Store(), payload, analysis_only='--analysis-only' in sys.argv)
    except Exception as exc:
        reason = 'Session Analyzer reviewer guard: ' + str(exc)
        if payload.get('hook_event_name', 'PreToolUse') == 'PreToolUse':
            result = {'hookSpecificOutput': {'hookEventName':'PreToolUse',
                'permissionDecision':'deny', 'permissionDecisionReason':reason}}
        else:
            result = {'hookSpecificOutput': {'hookEventName':'SubagentStart',
                'additionalContext':reason + '. Stop: review remains incomplete.'}}
    print(json.dumps(result))


if __name__ == '__main__':
    main()
