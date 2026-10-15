import copy
import json
from pathlib import Path

VERSION = "2.1.294"


def usage(input=10, write=20, read=30, output=40, thinking=12):
    u = {"input_tokens": input, "cache_creation_input_tokens": write, "cache_read_input_tokens": read,
         "output_tokens": output, "cache_creation": {"ephemeral_5m_input_tokens": write, "ephemeral_1h_input_tokens": 0},
         "speed": "standard", "service_tier": "standard"}
    if thinking is not None:
        u["output_tokens_details"] = {"thinking_tokens": thinking}
    return u


def response(i, *, session="session-a", agent=None, mid=None, request=None, block=0, u=None, content=None, version=VERSION):
    r = {"type": "assistant", "uuid": "event-" + str(i), "sessionId": session, "version": version,
         "timestamp": "2026-09-01T12:%02d:%02d.000Z" % (i // 60, i % 60), "apiBlockIndex": block,
         "requestId": request or "req-" + str(i), "message": {"id": mid or "msg-" + str(i), "model": "test-model",
             "usage": copy.deepcopy(u if u is not None else usage()),
             "content": content if content is not None else [{"type": "text", "text": "Synthetic fixture, not private data."}]}}
    if agent:
        r["agentId"] = agent
    return r


def call(i, name="Bash", args=None, tool_id=None, **kwargs):
    return response(i, content=[{"type": "tool_use", "id": tool_id or "tool-" + str(i), "name": name,
                                 "input": args if args is not None else {"command": "echo hello"}}], **kwargs)


def result(i, tool_id, text="ok", error=False, meta=None, session="session-a", version=VERSION):
    r = {"type": "user", "uuid": "event-" + str(i), "sessionId": session, "version": version,
         "timestamp": "2026-09-01T12:%02d:%02d.000Z" % (i // 60, i % 60),
         "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": text, "is_error": error}]}}
    if meta is not None:
        r["toolUseResult"] = meta
    return r


def write_log(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return Path(path)


def smoke_rows():
    rows = [response(0, u=usage(input=100, write=200, read=300, output=50, thinking=10))]
    for i in (1, 3, 5):
        rows.extend([call(i, args={"command": "python3 missing.py"}), result(i + 1, "tool-" + str(i), "Exit code 2\nfixture failure", True)])
    rows.extend([call(7, name="Read", args={"file_path": "/synthetic/example.txt"}), result(8, "tool-7", "fixture file")])
    return rows
