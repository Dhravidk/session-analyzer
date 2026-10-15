import argparse
import json
import os
import sys
from pathlib import Path

from ally_analyzer import cli as baseline_cli
from ally_analyzer.engine import analyze_dataset, export_report
from ally_analyzer.ingest import import_bundle
from ally_analyzer.store import Store
from ally_analyzer.util import AnalyzerError, canonical, strict_json

from .config import load_config
from .evidence import prepare, preview
from .pipeline import interpret, read_run, run_summary
from .report import compare, export_jev_report, write_new


def parser():
    p = baseline_cli.parser()
    p.prog = "ally-session-jev"
    p.description = "Baseline Ally Session Analyzer with a separate Jev interpretation layer."
    sub = next(a for a in p._actions if isinstance(a, argparse._SubParsersAction))
    for name in ("run", "analyze"):
        c = sub.choices[name]
        c.add_argument("--jev-config", help="Operator-authored Jev configuration JSON")
        c.add_argument("--skip-jev", action="store_true", help="Run baseline only; no Jev requests")
        c.add_argument("--fresh", action="store_true", help="Ignore saved Jev answers for this run")
    for name in ("jev-preview", "jev-interpret"):
        c = sub.add_parser(name, help="Preview requests locally" if name.endswith("preview") else "Send selected evidence to Jev")
        c.add_argument("analysis_id")
        c.add_argument("--config")
        if name.endswith("interpret"):
            c.add_argument("--fresh", action="store_true")
    c = sub.add_parser("jev-results", help="Read a persisted Jev run")
    c.add_argument("run_id")
    c = sub.add_parser("jev-export", help="Export the same baseline report with one exact Jev run")
    c.add_argument("run_id"); c.add_argument("destination")
    c = sub.add_parser("compare", help="Create matched A/B reports, timing manifest and team feedback CSV")
    c.add_argument("source"); c.add_argument("--output", required=True, help="New output directory")
    c.add_argument("--namespace", default="local")
    c.add_argument("--profile"); c.add_argument("--prices"); c.add_argument("--config")
    c.add_argument("--live", action="store_true", help="Call Jev; without this flag create a local preview only")
    c.add_argument("--fresh", action="store_true", help="Ignore saved Jev answers")
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(argv)
    if args.command not in ("run", "analyze", "compare", "jev-preview", "jev-interpret", "jev-results", "jev-export", "mcp"):
        return baseline_cli.main(argv)
    try:
        store = Store(args.data_dir)
        load = lambda path: strict_json(Path(path).read_text()) if path else None
        if args.command == "mcp":
            from .mcp import serve
            serve(store, args.allow_content or os.environ.get("ALLY_ANALYZER_ALLOW_CONTENT") == "1")
            return 0
        if args.command == "compare":
            result = compare(store, args.source, args.output, load_config(args.config), args.live,
                not args.fresh, args.namespace, load(args.profile), load(args.prices))
        elif args.command in ("jev-preview", "jev-interpret"):
            settings = load_config(args.config)
            result = preview(prepare(store, args.analysis_id, settings)) if args.command == "jev-preview" else run_summary(
                interpret(store, args.analysis_id, settings, not args.fresh))
        elif args.command in ("jev-results", "jev-export"):
            run = read_run(store, args.run_id)
            result = run if args.command == "jev-results" else export_jev_report(store, run["analysis_id"], run, args.destination)
        else:
            settings = load_config(args.jev_config)
            if args.command == "run":
                if args.output and (Path(args.output).exists() or Path(args.output + ".jev.json").exists()):
                    raise AnalyzerError("Report destination already exists")
                labels = {}
                for label in args.label:
                    if "=" not in label:
                        raise AnalyzerError("Labels use KEY=VALUE")
                    key, value = label.split("=", 1)
                    labels[key] = value
                result = import_bundle(store, args.source, args.namespace, labels)
                dataset_id = result["dataset_id"]
            else:
                dataset_id, result = args.dataset_id, {}
            result.update(analyze_dataset(store, dataset_id, load(args.profile), load(args.prices)))
            run = None
            if not args.skip_jev:
                run = interpret(store, result["analysis_id"], settings, not args.fresh)
                result["jev"] = run_summary(run)
            if args.command == "run" and args.output:
                if run and args.format == "html":
                    result["report"] = export_jev_report(store, result["analysis_id"], run, args.output)
                else:
                    result["report"] = export_report(store, result["analysis_id"], args.output, args.format)
                if run:
                    result["jev_results_path"] = write_new(args.output + ".jev.json", canonical(run) + "\n")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        status = result.get("jev_status", result.get("status", result.get("jev", {}).get("status")))
        return 3 if status in ("unavailable", "partial") else 0
    except (AnalyzerError, OSError, ValueError) as exc:
        print(canonical({"error": str(exc)}), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted; committed baseline results remain available.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
