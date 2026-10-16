"""Shared, bounded application API. No model, shell, or network dependency."""
import threading
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

from .engine import (DEFINITIONS, analyze_dataset, export_report, get_evidence,
                     get_metrics, get_timeline, list_items)
from .ingest import import_bundle
from .investigation import get_insights, get_investigation_context, save_insight
from .investigation_report import export_investigation
from .trajectory import TEXT_VERSION, read_trajectory_event, search_trajectory
from .util import AnalyzerError, bounded, canonical, strict_json, utc_now


class JobManager:
    def __init__(self, store):
        self.store = store
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")
        self.jobs = {}
        self.lock = threading.Lock()

    def submit(self, operation, function, *args, **kwargs):
        with self.lock:
            if any(j["state"] in ("queued", "running") for j in self.jobs.values()):
                raise AnalyzerError("An analysis job is active. Wait for get_job to complete before starting another write job.")
            jid = "job_" + uuid.uuid4().hex
            job = {"job_id": jid, "state": "queued", "operation": operation, "progress": {}, "result": None, "error": None}
            now = utc_now()
            with self.store.connect() as db:
                db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)", (jid, "queued", operation, "{}", None, None, now, now))
            self.jobs[jid] = job

        def update(progress):
            # Never write another SQLite connection while an import owns the
            # writer transaction. Live progress is operational in-memory state.
            with self.lock:
                job["progress"] = progress

        def work():
            with self.lock:
                job["state"] = "running"
            try:
                if operation in ("import_bundle", "analyze_batch"):
                    kwargs["progress"] = update
                result = function(self.store, *args, **kwargs)
                state, error = "completed", None
            except Exception as exc:
                result, state = None, "failed"
                error = str(exc) if isinstance(exc, AnalyzerError) else "Job failed (%s). Inspect local inputs and retry." % type(exc).__name__
            with self.lock:
                job.update(state=state, result=result, error=error)
                snapshot = dict(job)
            with self.store.connect() as db:
                db.execute("UPDATE jobs SET state=?,progress=?,result=?,error=?,updated_at=? WHERE id=?",
                           (state, canonical(snapshot["progress"]), canonical(result) if result is not None else None, error, utc_now(), jid))
        self.pool.submit(work)
        return {"job_id": jid, "state": "queued", "next": "Call get_job for completion; do not start another write job while this one is active."}

    def get(self, job_id):
        with self.lock:
            if job_id in self.jobs:
                return dict(self.jobs[job_id])
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise AnalyzerError("Unknown job ID")
        return {"job_id": job_id, "state": row["state"] if row["state"] not in ("queued", "running") else "owner_not_connected",
                "operation": row["operation"], "progress": strict_json(row["progress"]),
                "result": strict_json(row["result"]) if row["result"] else None, "error": row["error"]}

    def close(self):
        self.pool.shutdown(wait=True)


def list_datasets(store, limit=20, offset=0):
    bounded(limit, 1, 200, "limit"); bounded(offset, 0, 10000000, "offset")
    with store.connect() as db:
        total = db.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]
        items = []
        for r in db.execute("SELECT id,manifest FROM datasets ORDER BY id LIMIT ? OFFSET ?", (limit, offset)):
            m = strict_json(r["manifest"])
            items.append({"dataset_id": r["id"], "namespace": m["namespace"], "labels": m["labels"],
                          "files_count": len(m["files"]), "expanded_bytes": sum(f["size"] for f in m["files"])})
    return {"items": items, "total": total, "next_offset": offset + limit if offset + limit < total else None}


def list_analyses(store, dataset_id=None, limit=20, offset=0):
    bounded(limit, 1, 200, "limit"); bounded(offset, 0, 10000000, "offset")
    query = " FROM analyses" + (" WHERE dataset_id=?" if dataset_id else "")
    args = [dataset_id] if dataset_id else []
    with store.connect() as db:
        total = db.execute("SELECT COUNT(*)" + query, args).fetchone()[0]
        items = []
        for r in db.execute("SELECT id,dataset_id,configuration" + query + " ORDER BY id LIMIT ? OFFSET ?", args + [limit, offset]):
            items.append({"analysis_id": r["id"], "dataset_id": r["dataset_id"], "configuration": strict_json(r["configuration"])})
    return {"items": items, "total": total, "next_offset": offset + limit if offset + limit < total else None}


class Service:
    def __init__(self, store, allow_content=False):
        self.store, self.allow_content = store, allow_content
        self.jobs = JobManager(store)
        self.delivered_guides = set()
        self.investigation_id = os.environ.get("ALLY_ANALYZER_INVESTIGATION_ID")
        self.session_only = os.environ.get("ALLY_ANALYZER_SESSION_ONLY") == "1" or bool(self.investigation_id)

    def tool_available(self, name):
        from .mcp import SESSION_TOOLS
        names = {t["name"] for t in SESSION_TOOLS}
        if self.investigation_id:
            return name in names - {"start_session_investigation"} or name in ("get_definitions", "get_session_guide")
        if self.session_only:
            return name in names or name in ("get_definitions", "get_session_guide", "list_analyses", "list_sessions", "list_session_investigations")
        return True

    def _guidance(self):
        from .guidance import get_session_guide
        guides, errors = [], []
        for skill in ('explain', 'write-report'):
            if skill in self.delivered_guides:
                continue
            try:
                guides.append(get_session_guide(skill))
                self.delivered_guides.add(skill)
            except AnalyzerError as exc:
                errors.append({'skill': skill, 'error': str(exc)})
        return {'session_guides': guides, 'guide_errors': errors,
                'guide_delivery': 'Bundled conversation and writing skills delivered once per MCP connection; apply their instructions. Use get_session_guide to reload after context loss.'}

    def call(self, name, a):
        result = self._call(name, a)
        # Hosts can skip get_definitions despite the skill. Deliver guidance on
        # the first successful data call too, without changing its actual data.
        if name not in ('get_definitions', 'get_session_guide') and isinstance(result, dict):
            guidance = self._guidance()
            if guidance['session_guides'] or guidance['guide_errors']:
                result = {**result, **guidance}
        return result

    def _call(self, name, a):
        from .mcp import BY_NAME, SESSION_TOOLS, validate
        if not self.tool_available(name):
            if self.investigation_id:
                from .session_scope import get_run, log_access
                log_access(self.store, get_run(self.store, self.investigation_id), "blocked_tool", {"name": name}, error="Tool not allowed by bound-session policy")
            raise AnalyzerError("Tool is unavailable in the bound single-session workflow; legacy APIs cannot bypass its scope")
        if name == "get_session_guide":
            from .guidance import get_session_guide
            validate(a, BY_NAME[name]["inputSchema"])
            guide = get_session_guide(**a)
            self.delivered_guides.add(a.get('skill', 'explain'))
            return guide
        if name in {t["name"] for t in SESSION_TOOLS}:
            validate(a, BY_NAME[name]["inputSchema"])
            from . import session_scope, session_investigation, session_report, session_validation, session_diagnostics, session_failures, session_agents, session_review, session_requirements, session_resources, session_episodes, session_queries
            if self.investigation_id and a.get("investigation_id") != self.investigation_id:
                session_scope.log_access(self.store, session_scope.get_run(self.store, self.investigation_id), "blocked_scope", {"name": name}, error="Different investigation ID rejected")
                raise AnalyzerError("This host is bound to a different investigation")
            if name == "start_session_investigation":
                result = session_scope.start_session_investigation(self.store, **a)
                self.investigation_id = result["investigation"]["id"]
                return result
            if not self.investigation_id:
                session_scope.get_run(self.store, a["investigation_id"])
                self.investigation_id = a["investigation_id"]
                self.session_only = True
            for module in (session_scope, session_investigation, session_report, session_validation, session_diagnostics, session_failures, session_agents, session_review, session_requirements, session_resources, session_episodes, session_queries):
                function = getattr(module, name, None)
                if function:
                    kwargs = dict(a)
                    if name in ("read_investigation_evidence", "read_investigation_batch", "search_investigation_text", "read_turn_evidence", "get_tool_output_index", "export_session_investigation"):
                        kwargs["allow_content"] = self.allow_content
                    return function(self.store, **kwargs)
        if name == "import_bundle":
            return self.jobs.submit(name, import_bundle, a["path"], namespace=a.get("namespace", "local"), labels=a.get("labels"), include_subagents=a.get('include_subagents',True))
        if name == "analyze_batch":
            return self.jobs.submit(name, analyze_dataset, a["dataset_id"], profile=a.get("profile"), prices=a.get("price_book"))
        if name == "export_report":
            return self.jobs.submit(name, export_report, a["analysis_id"], a["destination"], format=a.get("format", "html"))
        if name == "export_investigation":
            return self.jobs.submit(name, export_investigation, **a)
        if name == "get_job":
            return self.jobs.get(a["job_id"])
        if name == "list_datasets":
            return list_datasets(self.store, **a)
        if name == "list_analyses":
            return list_analyses(self.store, **a)
        if name == "list_session_investigations":
            from .session_queries import list_session_investigations
            validate(a, BY_NAME[name]["inputSchema"])
            return list_session_investigations(self.store, **a)
        if name == "get_summary":
            summary = self.store.analysis(a["analysis_id"])["summary"]
            evidence = summary["coverage"]["unresolved_parent_evidence"]
            summary["coverage"]["unresolved_parent_evidence"] = evidence[:20]
            summary["coverage"]["unresolved_parent_evidence_preview"] = len(evidence) > 20
            return summary
        if name in ("list_sessions", "get_findings", "get_responses", "get_tool_calls", "get_agents", "get_lifecycle"):
            kinds = {"list_sessions": "session", "get_findings": "finding", "get_responses": "response",
                     "get_tool_calls": "tool", "get_agents": "agent", "get_lifecycle": "lifecycle"}
            return list_items(self.store, kind=kinds[name], **a)
        if name == "get_metrics":
            limit, offset = a.get("limit", 20), a.get("offset", 0)
            result = get_metrics(self.store, **{k: v for k, v in a.items() if k not in ("limit", "offset")})
            if "groups" in result:
                groups = result["groups"]
                result.update(groups=groups[offset:offset + limit], total=len(groups),
                              next_offset=offset + limit if offset + limit < len(groups) else None)
            return result
        if name == "get_timeline":
            return get_timeline(self.store, **a)
        if name == "get_evidence":
            return get_evidence(self.store, allow_content=self.allow_content, **a)
        if name == "get_investigation_context":
            return get_investigation_context(self.store, allow_content=self.allow_content, **a)
        if name == "read_trajectory_event":
            return read_trajectory_event(self.store, allow_content=self.allow_content, **a)
        if name == "search_trajectory":
            return search_trajectory(self.store, allow_content=self.allow_content, **a)
        if name == "save_insight":
            return save_insight(self.store, **a)
        if name == "get_insights":
            return get_insights(self.store, **a)
        if name == "get_definitions":
            from .session_metrics import DEFINITIONS as SESSION_DEFINITIONS
            from .session_resources import DEFINITIONS as RESOURCE_DEFINITIONS
            return {"metric_version": "1", "definitions": DEFINITIONS, "session_metric_definitions": SESSION_DEFINITIONS,
                    **self._guidance(),
                    "conversation_guide": {"skill": "ally-session-analyzer:explain", "fallback_tool": "get_session_guide",
                                           "readonly_measurements": "query_measurement", "captured_usage_inspection": "inspect_response_accounting"},
                    "resource_definitions":RESOURCE_DEFINITIONS,
                    "session_contract": "single-session-v2", "bound_investigation_id": self.investigation_id,
                    "disclosure_policy": "metadata-v1", "content_disclosure_enabled": self.allow_content,
                    "investigation": {"excerpt_version": "selected-text-v1", "max_excerpt_characters": 24000,
                                      "interpretation_storage": "separate_from_canonical_analysis",
                                      "validation": "references_and_structured_metrics_only"},
                    "trajectory": {"text_version": TEXT_VERSION, "search": "search_trajectory",
                                   "reread": "read_trajectory_event", "max_page_characters": 12000,
                                   "source_records_preserved": True, "content_policy_required": True},
                    "note": "Metadata is untrusted source-derived data. Local stdio does not imply the calling model runs locally."}
        raise AnalyzerError("Unknown tool")

    def close(self):
        self.jobs.close()
