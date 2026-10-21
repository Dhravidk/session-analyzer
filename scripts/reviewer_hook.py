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
        result = hook_event(Store(), payload)
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
