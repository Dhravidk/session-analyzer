import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .engine import (DEFINITIONS, analyze_dataset, export_report, get_evidence,
                     get_metrics, get_timeline, list_items)
from .ingest import import_bundle
from .investigation import REVIEW_STATUSES, get_insights, get_investigation_context, review_insight, save_insight
from .investigation_report import export_investigation
from .service import list_analyses, list_datasets
from .store import Store
from .trajectory import read_trajectory_event, search_trajectory
from .util import AnalyzerError, canonical, strict_json, utc_now


def parser():
    p = argparse.ArgumentParser(prog="ally-session", description="Offline, deterministic Claude Code session analysis.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--data-dir", help="Private analysis store (default: ALLY_ANALYZER_HOME or ~/.ally-session-analyzer)")
    sub = p.add_subparsers(dest="command", required=True)
    def source_args(c):
        c.add_argument("source", help="Selected ZIP, directory or JSONL/.log file")
        c.add_argument("--namespace", default="local", help="Dataset owner/collection boundary")
        c.add_argument("--label", action="append", default=[], metavar="KEY=VALUE")
        c.add_argument("--parent-only", action="store_true", help="Do not collect the selected file's adjacent session/subagents logs")
    def analysis_args(c):
        c.add_argument("--profile", help="JSON rule profile")
        c.add_argument("--prices", help="Explicit, versioned JSON rate card; omitted by default")
    source_args(sub.add_parser("import", help="Snapshot and index a selected input"))
    a = sub.add_parser("analyze", help="Analyze an imported dataset")
    a.add_argument("dataset_id"); analysis_args(a)
    a = sub.add_parser("run", help="Import, analyze and optionally export in one command")
    source_args(a); analysis_args(a)
    a.add_argument("--output", help="New report filename; existing files are never overwritten")
    a.add_argument("--format", choices=["html", "json", "csv"], default="html")
    for command in ("datasets", "analyses"):
        a = sub.add_parser(command)
        a.add_argument("--limit", type=int, default=20); a.add_argument("--offset", type=int, default=0)
        if command == "analyses":
            a.add_argument("--dataset-id")
    a = sub.add_parser("summary"); a.add_argument("analysis_id")
    a = sub.add_parser("metrics"); a.add_argument("analysis_id")
    a.add_argument("--session-id"); a.add_argument("--group-by", choices=["model", "tool", "session"])
    for command in ("sessions", "responses", "tools", "findings", "agents", "lifecycle"):
        a = sub.add_parser(command); a.add_argument("analysis_id")
        a.add_argument("--session-id"); a.add_argument("--search")
        a.add_argument("--limit", type=int, default=50); a.add_argument("--offset", type=int, default=0)
    a = sub.add_parser("timeline"); a.add_argument("analysis_id"); a.add_argument("session_id")
    a.add_argument("--limit", type=int, default=100); a.add_argument("--offset", type=int, default=0)
    a = sub.add_parser("evidence"); a.add_argument("dataset_id"); a.add_argument("event_id")
    a.add_argument("--content", action="store_true", help="Explicitly disclose bounded raw content locally")
    a.add_argument("--max-chars", type=int, default=8000)
    a = sub.add_parser("export"); a.add_argument("analysis_id"); a.add_argument("destination")
    a.add_argument("--format", choices=["html", "json", "csv"], default="html")
    a = sub.add_parser("annotate", help="Record a human review separately from canonical findings")
    a.add_argument("analysis_id"); a.add_argument("finding_id")
    a.add_argument("--status", required=True, choices=["accepted", "dismissed", "needs_review"])
    a.add_argument("--note", default="")
    a = sub.add_parser("annotations"); a.add_argument("analysis_id")
    a = sub.add_parser("context", help="Inspect bounded investigation context around an event")
    a.add_argument("analysis_id"); a.add_argument("event_id")
    a.add_argument("--before", type=int, default=3); a.add_argument("--after", type=int, default=5)
    a.add_argument("--content", action="store_true", help="Explicitly disclose selected, masked text locally")
    a.add_argument("--max-chars", type=int, default=12000)
    a = sub.add_parser("trajectory-read", help="Explicitly disclose a page of retained, masked event text locally")
    a.add_argument("analysis_id"); a.add_argument("event_id")
    a.add_argument("--start-char", type=int, default=0); a.add_argument("--max-chars", type=int, default=8000)
    a.add_argument("--expected-text-sha256")
    a = sub.add_parser("trajectory-search", help="Explicitly search retained, masked transcript text locally")
    a.add_argument("analysis_id"); a.add_argument("query")
    a.add_argument("--session-id"); a.add_argument("--agent-id")
    a.add_argument("--limit", type=int, default=10); a.add_argument("--scan-offset", type=int, default=0)
    a.add_argument("--max-scan", type=int, default=1000)
    a = sub.add_parser("save-insight", help="Validate and save a suggested interpretation separately")
    a.add_argument("analysis_id"); a.add_argument("insight_json")
    a = sub.add_parser("insights", help="Read saved interpretations and latest reviews")
    a.add_argument("analysis_id"); a.add_argument("--limit", type=int, default=20); a.add_argument("--offset", type=int, default=0)
    a = sub.add_parser("review-insight", help="Append an operator review; does not change engine findings")
    a.add_argument("insight_id"); a.add_argument("--status", required=True, choices=REVIEW_STATUSES)
    a.add_argument("--note", required=True)
    a = sub.add_parser("export-investigation", help="Export saved recommendations to an offline report")
    a.add_argument("analysis_id"); a.add_argument("destination")
    a.add_argument("--format", choices=["html", "json"], default="html")
    sub.add_parser("definitions")
    sub.add_parser("investigate", help="Run an approved Claude investigation and independent evidence review", add_help=False)
    sub.add_parser("browse", help="Open a local session directory and its saved reports", add_help=False)
    a = sub.add_parser("session-start", help="Start an immutable single-session investigation")
    a.add_argument("analysis_id"); a.add_argument("session_id")
    a.add_argument("--purpose", required=True); a.add_argument("--artifact-id", action="append", default=[])
    a.add_argument("--revision-of")
    a = sub.add_parser("session-call", help="Call a scoped investigation API using a JSON arguments file")
    a.add_argument("operation"); a.add_argument("arguments_json")
    a.add_argument("--allow-content", action="store_true")
    a = sub.add_parser("session-overview"); a.add_argument("investigation_id")
    a = sub.add_parser("export-session"); a.add_argument("investigation_id"); a.add_argument("destination")
    a.add_argument("--format", choices=["html", "json"], default="html")
    a.add_argument("--include-source-text", action="store_true", help="Embed full retained masked source text for offline evidence navigation")
    a = sub.add_parser("admit-artifact", help="Operator only: snapshot a selected instruction, target or candidate")
    a.add_argument("path"); a.add_argument("--label", required=True)
    a.add_argument("--temporal-relation", required=True, choices=["historical", "current", "proposed"])
    a.add_argument("--completeness", required=True, choices=["complete", "partial"]); a.add_argument("--version")
    a = sub.add_parser("revise-scope", help="Operator only: create a linked scope revision with selected new evidence")
    a.add_argument("investigation_id"); a.add_argument("--artifact-id", action="append", default=[]); a.add_argument("--analysis-id")
    a = sub.add_parser("fixture-check", help="Operator only: execute a reviewed local fixture plan against a bound candidate")
    a.add_argument("investigation_id"); a.add_argument("recommendation_id")
    a.add_argument("--fixture-dir", required=True); a.add_argument("--plan", required=True)
    a = sub.add_parser("review-recommendation", help="Operator only: record acceptance or a reported outcome separately")
    a.add_argument("investigation_id"); a.add_argument("recommendation_id"); a.add_argument("--status", required=True)
    a.add_argument("--note", required=True); a.add_argument("--check-id", action="append", default=[])
    a = sub.add_parser("mcp", help="Serve the same engine over local MCP stdio")
    a.add_argument("--allow-content", action="store_true", help="Operator opt-in to raw excerpt disclosure; off by default")
    return p


def main(argv=None):
    arguments = list(argv) if argv is not None else sys.argv[1:]
    if arguments and arguments[0] == 'browse':
        from .session_library import main as browse
        return browse(arguments[1:])
    if arguments and arguments[0] == 'investigate':
        from .claude_runner import main as investigate
        return investigate(arguments[1:])
    args = parser().parse_args(arguments)
    def load(path):
        return strict_json(Path(path).read_bytes()) if path else None
    def labels():
        result = {}
        for label in args.label:
            if "=" not in label:
                raise AnalyzerError("Labels use KEY=VALUE")
            k, v = label.split("=", 1); result[k] = v
        return result
    try:
        store = Store(args.data_dir)
        c = args.command
        if c == "mcp":
            from .mcp import serve
            serve(store, args.allow_content or os.environ.get("ALLY_ANALYZER_ALLOW_CONTENT") == "1")
            return 0
        if c in ("import", "run"):
            result = import_bundle(store, args.source, args.namespace, labels(), include_subagents=not args.parent_only)
            if c == "run":
                result.update(analyze_dataset(store, result["dataset_id"], load(args.profile), load(args.prices)))
                if args.output:
                    result["report"] = export_report(store, result["analysis_id"], args.output, args.format)
        elif c == "analyze":
            result = analyze_dataset(store, args.dataset_id, load(args.profile), load(args.prices))
        elif c == "datasets":
            result = list_datasets(store, args.limit, args.offset)
        elif c == "analyses":
            result = list_analyses(store, args.dataset_id, args.limit, args.offset)
        elif c == "summary":
            result = store.analysis(args.analysis_id)["summary"]
        elif c == "metrics":
            result = get_metrics(store, args.analysis_id, args.session_id, args.group_by)
        elif c in ("sessions", "responses", "tools", "findings", "agents", "lifecycle"):
            kinds = {"sessions": "session", "responses": "response", "tools": "tool", "findings": "finding", "agents": "agent", "lifecycle": "lifecycle"}
            result = list_items(store, args.analysis_id, kinds[c], args.session_id, args.limit, args.offset, args.search)
        elif c == "timeline":
            result = get_timeline(store, args.analysis_id, args.session_id, args.limit, args.offset)
        elif c == "evidence":
            result = get_evidence(store, args.dataset_id, args.event_id, args.content, True, args.max_chars)
        elif c == "export":
            result = export_report(store, args.analysis_id, args.destination, args.format)
        elif c == "context":
            result = get_investigation_context(store, args.analysis_id, args.event_id, args.before, args.after, args.content, args.max_chars, True)
        elif c == "trajectory-read":
            result = read_trajectory_event(store, args.analysis_id, args.event_id, args.start_char,
                                           args.max_chars, args.expected_text_sha256, allow_content=True)
        elif c == "trajectory-search":
            result = search_trajectory(store, args.analysis_id, args.query, args.session_id, args.agent_id,
                                       args.limit, args.scan_offset, args.max_scan, allow_content=True)
        elif c == "save-insight":
            result = save_insight(store, args.analysis_id, load(args.insight_json))
        elif c == "insights":
            result = get_insights(store, args.analysis_id, args.limit, args.offset)
        elif c == "review-insight":
            result = review_insight(store, args.insight_id, args.status, args.note)
        elif c == "export-investigation":
            result = export_investigation(store, args.analysis_id, args.destination, args.format)
        elif c == "definitions":
            result = DEFINITIONS
        elif c == "session-start":
            from .session_scope import start_session_investigation
            result = start_session_investigation(store, args.analysis_id, args.session_id, args.purpose,
                                                 revision_of=args.revision_of, artifact_ids=args.artifact_id)
        elif c == "session-call":
            from .service import Service
            from .mcp import SESSION_TOOLS
            if args.operation not in {t["name"] for t in SESSION_TOOLS}:
                raise AnalyzerError("session-call accepts only scoped investigation APIs")
            service = Service(store, allow_content=args.allow_content)
            try:
                result = service.call(args.operation, load(args.arguments_json))
            finally:
                service.close()
        elif c == "session-overview":
            from .session_investigation import get_session_overview
            result = get_session_overview(store, args.investigation_id)
        elif c == "export-session":
            from .session_report import export_session_investigation
            result = export_session_investigation(store, args.investigation_id, args.destination, args.format,
                                                 include_source_text=args.include_source_text, allow_content=args.include_source_text)
        elif c == "admit-artifact":
            from .session_validation import admit_artifact
            result = admit_artifact(store, args.path, args.label, args.temporal_relation, args.completeness, args.version)
        elif c == "revise-scope":
            from .session_validation import revise_scope
            result = revise_scope(store, args.investigation_id, args.artifact_id, args.analysis_id)
        elif c == "fixture-check":
            from .session_validation import run_fixture_checks
            result = run_fixture_checks(store, args.investigation_id, args.recommendation_id, args.fixture_dir, args.plan)
        elif c == "review-recommendation":
            from .session_validation import review_recommendation
            result = review_recommendation(store, args.investigation_id, args.recommendation_id, args.status, args.note, args.check_id)
        elif c == "annotate":
            if len(args.note) > 4000:
                raise AnalyzerError("Note must be at most 4,000 characters")
            store.analysis(args.analysis_id)
            with store.connect() as db:
                if not db.execute("SELECT 1 FROM items WHERE analysis_id=? AND kind='finding' AND id=?", (args.analysis_id, args.finding_id)).fetchone():
                    raise AnalyzerError("Unknown finding ID")
                db.execute("INSERT OR REPLACE INTO annotations VALUES (?,?,?,?,?)", (args.analysis_id, args.finding_id, args.status, args.note, utc_now()))
            result = {"finding_id": args.finding_id, "status": args.status, "canonical_finding_unchanged": True}
        elif c == "annotations":
            store.analysis(args.analysis_id)
            with store.connect() as db:
                result = {"annotations": [dict(r) for r in db.execute("SELECT * FROM annotations WHERE analysis_id=? ORDER BY finding_id", (args.analysis_id,))]}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        return 0
    except (AnalyzerError, OSError, ValueError) as exc:
        print(canonical({"error": str(exc)}), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('Interrupted; committed imports and analyses remain available.', file=sys.stderr)
        return 130
