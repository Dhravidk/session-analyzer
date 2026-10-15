"""Reuse baseline tools/protocol; add explicitly named Jev operations."""
import os
import sys

from ally_analyzer import mcp as base
from ally_analyzer.service import Service as BaselineService
from ally_analyzer.util import AnalyzerError, bounded, canonical, strict_json

from .config import load_config
from .evidence import prepare, preview
from .pipeline import interpret, read_run, run_summary
from .report import export_jev_report


def extra_spec(name, description, props, required, read=True, remote=False):
    result = base.spec(name, description, props, required, read, not remote)
    result["annotations"]["openWorldHint"] = remote
    return result


EXTRA = [
    extra_spec("jev_preview", "Prepare a bounded Jev request inventory locally. No network calls or source excerpts returned. Operator configuration controls what a live run would disclose.", {"analysis_id": base.S}, ["analysis_id"]),
    extra_spec("jev_interpret", "Explicitly send selected evidence to TypeSafe Jev for optional prompt classifications and review priorities. Requires operator enablement and credentials. Returns a job ID. Counts and rule findings remain unchanged.",
        {"analysis_id": base.S, "fresh": {"type": "boolean", "default": False}}, ["analysis_id"], False, True),
    extra_spec("jev_get_run", "Read a Jev run's status, configuration, request coverage, timing and usage. Missing judgments are unknown.", {"run_id": base.S}, ["run_id"]),
    extra_spec("jev_get_annotations", "Read paginated Jev interpretations and their evidence references; no source excerpts. Probability and distribution confidence are distinct. Interpretations never establish human authorship or proven waste.",
        {"run_id": base.S, **base.PAGE}, ["run_id"]),
    extra_spec("jev_export_report", "Create the unchanged baseline HTML report plus a separate Jev review panel for one exact run. No new Jev calls; refuses overwrite. Returns a job ID.",
        {"run_id": base.S, "destination": base.S}, ["run_id", "destination"], False),
]
EXTRA_BY_NAME = {t["name"]: t for t in EXTRA}


class Service(BaselineService):
    def __init__(self, store, allow_content=False, enabled=None, settings=None):
        super().__init__(store, allow_content)
        self.enabled = os.environ.get("ALLY_JEV_ENABLED") == "1" if enabled is None else enabled
        self.settings = settings if settings is not None else load_config(os.environ.get("ALLY_JEV_CONFIG"))

    def call(self, name, a):
        if name == "jev_preview":
            return preview(prepare(self.store, a["analysis_id"], self.settings))
        if name == "jev_interpret":
            if not self.enabled:
                raise AnalyzerError("Jev calls are disabled. The operator must set ALLY_JEV_ENABLED=1 outside the agent process.")
            def work(store):
                return run_summary(interpret(store, a["analysis_id"], self.settings, not a.get("fresh", False)))
            return self.jobs.submit(name, work)
        if name in ("jev_get_run", "jev_get_annotations", "jev_export_report"):
            run = read_run(self.store, a["run_id"])
            if name == "jev_get_run":
                return run_summary(run)
            if name == "jev_get_annotations":
                limit, offset = a.get("limit", 20), a.get("offset", 0)
                bounded(limit, 1, 200, "limit"); bounded(offset, 0, 10000000, "offset")
                annotations = run["annotations"]
                return {"run_id": a["run_id"], "items": annotations[offset:offset + limit], "total": len(annotations),
                        "next_offset": offset + limit if offset + limit < len(annotations) else None}
            return self.jobs.submit(name, export_jev_report, run["analysis_id"], run, a["destination"])
        return super().call(name, a)


class Protocol(base.Protocol):
    def handle(self, request):
        valid = isinstance(request, dict) and request.get("jsonrpc") == "2.0" and isinstance(request.get("id"), (int, str)) and not isinstance(request.get("id"), bool)
        params = request.get("params", {}) if valid else {}
        name = params.get("name") if isinstance(params, dict) else None
        if valid and self.initialized and request.get("method") == "tools/call" and isinstance(name, str) and name in EXTRA_BY_NAME:
            try:
                args = params.get("arguments", {})
                base.validate(args, EXTRA_BY_NAME[name]["inputSchema"])
                value = self.service.call(name, args)
                content = canonical(value)
                if len(content.encode("utf-8")) > base.MAX_RESULT_BYTES:
                    raise AnalyzerError("Result too large; use a smaller page")
                result = {"content": [{"type": "text", "text": content}], "isError": False}
                if self.version == "2025-06-18":
                    result["structuredContent"] = value
            except AnalyzerError as exc:
                result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
            except Exception:
                result = {"content": [{"type": "text", "text": "Jev operation failed; inspect local configuration."}], "isError": True}
            return {"jsonrpc": "2.0", "id": request["id"], "result": result}
        response = super().handle(request)
        if response and "result" in response and isinstance(request, dict):
            if request.get("method") == "tools/list":
                response["result"]["tools"] = response["result"]["tools"] + EXTRA
            elif request.get("method") == "initialize":
                response["result"]["serverInfo"]["name"] = "ally-session-analyzer-jev"
                response["result"]["instructions"] += " Jev tools produce optional interpretations. Call jev_interpret only when the user requests Jev analysis."
        return response


def serve(store, allow_content=False, reader=None, writer=None):
    service = Service(store, allow_content)
    protocol = Protocol(service)
    reader, writer = reader or sys.stdin.buffer, writer or sys.stdout
    try:
        while True:
            line = reader.readline(base.MAX_MESSAGE_BYTES + 1)
            if not line:
                break
            if not line.strip():
                continue
            try:
                if len(line) > base.MAX_MESSAGE_BYTES:
                    while line and not line.endswith(b"\n"):
                        line = reader.readline(base.MAX_MESSAGE_BYTES + 1)
                    raise ValueError("Oversized request")
                response = protocol.handle(strict_json(line))
            except (ValueError, UnicodeError, RecursionError):
                response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Invalid or oversized JSON"}}
            if response is not None:
                writer.write(canonical(response) + "\n")
                writer.flush()
    finally:
        service.close()
