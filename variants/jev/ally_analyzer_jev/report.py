import hashlib
import html
import tempfile
import time
from pathlib import Path

import ally_analyzer
from ally_analyzer.engine import analyze_dataset, canonical_report, export_report, get_evidence
from ally_analyzer.ingest import import_bundle
from ally_analyzer.util import AnalyzerError, canonical, digest

from .evidence import prepare, preview
from .pipeline import interpret


def write_new(path, text):
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as out:
        out.write(text)
    path.chmod(0o600)
    return str(path)


def json_for_html(value):
    return canonical(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def export_jev_report(store, analysis_id, run, destination):
    baseline = canonical_report(store, analysis_id)
    if run["analysis_id"] != analysis_id or run["baseline_sha256"] != digest(baseline):
        raise AnalyzerError("Jev run does not match this exact baseline analysis")
    path = Path(destination).expanduser().resolve()
    if path == store.db_path or path == store.objects or store.objects in path.parents or store.root / "jev" in path.parents:
        raise AnalyzerError("Report cannot overwrite analysis storage")
    # Delegate rendering as well as accounting. New baseline placeholders or
    # runtime settings must be populated by the same exporter used by version A.
    with tempfile.TemporaryDirectory(prefix="ally-jev-report-") as temporary:
        rendered = Path(temporary) / "baseline.html"
        export_report(store, analysis_id, rendered)
        base_html = rendered.read_text()
    refs = {eid for annotation in run["annotations"] for eid in annotation.get("evidence", [])}
    evidence = {eid: get_evidence(store, baseline["summary"]["dataset_id"], eid) for eid in sorted(refs)}
    extension = Path(__file__).with_name("panel.html").read_text().replace("__JEV_JSON__", json_for_html({**run, "evidence": evidence}))
    if "</body>" not in base_html:
        raise AnalyzerError("Baseline report template has changed; update the Jev report adapter")
    write_new(path, base_html.replace("</body>", extension + "</body>", 1))
    return {"path": str(path), "format": "html", "analysis_id": analysis_id,
            "run_id": run.get("run_id"), "raw_content_included": False, "variant": "jev"}


def source_fingerprint():
    root = Path(ally_analyzer.__file__).parent
    files = sorted(list(root.glob("*.py")) + list(root.glob("*.html")))
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def compare(store, source, output, settings=None, live=False, use_cache=True, namespace="local", profile=None, prices=None, client=None):
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise AnalyzerError("Comparison output already exists; choose a new directory")
    # Check template availability before importing or sending any requests.
    if not Path(ally_analyzer.__file__).with_name("report.html").is_file():
        raise AnalyzerError("The baseline HTML report must be installed before making an A/B comparison")
    start = time.perf_counter()
    imported = import_bundle(store, source, namespace=namespace)
    analyzed = analyze_dataset(store, imported["dataset_id"], profile=profile, prices=prices)
    core_seconds = time.perf_counter() - start
    analysis_id = analyzed["analysis_id"]
    baseline = canonical_report(store, analysis_id)
    before = digest(baseline)
    if live:
        run = interpret(store, analysis_id, settings, use_cache, client)
    else:
        plan = prepare(store, analysis_id, settings)
        run = {**preview(plan), "status": "not_run", "variant": "jev", "run_id": None,
               "annotations": [], "operational": {},
               "limitations": ["Prepared locally only. No Jev judgments have been made; this is not a model-quality comparison."]}
    if digest(canonical_report(store, analysis_id)) != before:
        raise AnalyzerError("Canonical results changed; comparison aborted")
    output.mkdir(parents=True, mode=0o700)
    export_report(store, analysis_id, output / "A-baseline.html")
    export_jev_report(store, analysis_id, run, output / "B-jev.html")
    write_new(output / "baseline.json", canonical(baseline) + "\n")
    write_new(output / "jev.json", canonical(run) + "\n")
    manifest = {"analysis_id": analysis_id, "dataset_id": imported["dataset_id"],
        "canonical_sha256_A": before, "canonical_sha256_B": before, "canonical_results_identical": True,
        "baseline_source_sha256": source_fingerprint(), "baseline_configuration": baseline["summary"]["configuration"],
        "jev_configuration": run["configuration"], "jev_prompt_version": run["prompt_version"],
        "jev_run_id": run.get("run_id"), "jev_status": run["status"],
        "timing": {"shared_import_and_analysis_seconds": round(core_seconds, 6),
            "import_reused": imported["reused"], "analysis_reused": analyzed["reused"],
            "jev_seconds": run["operational"].get("elapsed_seconds"),
            "note": "The exact same core result is used by both variants. Shared work is measured once; report rendering is excluded. Cache reuse is explicit. These are not independent cold-run benchmarks."},
        "files": {"A": "A-baseline.html", "B": "B-jev.html", "canonical": "baseline.json", "interpretations": "jev.json"}}
    write_new(output / "comparison.json", canonical(manifest) + "\n")
    write_new(output / "feedback.csv", "reviewer,task,first_variant,variant,review_seconds,useful_findings,false_positives,missed_issues,trust_1_to_5,preferred_variant,notes\n")
    status = html.escape(run["status"])
    index = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'">
<title>Ally Session Analyzer · A/B comparison</title><style>body{font:17px/1.6 system-ui;background:#f4f5ef;color:#173d35;margin:50px auto;padding:0 24px;max-width:900px}a{color:#23664f}.cards{display:flex;gap:20px;flex-wrap:wrap}.card{background:white;border:1px solid #dce3da;border-radius:12px;padding:25px;flex:1;min-width:200px}h1{line-height:1.15}small{color:#64736c}li{margin:10px 0}</style>
<p>ALLY / SESSION ANALYZER</p><h1>Compare the same analysis.</h1><p>Both versions use identical source data, parsing, accounting, detection rules, and the same report. Version B adds optional Jev interpretations.</p>
<div class="cards"><section class="card"><h2>Version A</h2><p>Baseline evidence and deterministic findings.</p><a href="A-baseline.html">Open version A →</a></section><section class="card"><h2>Version B</h2><p>The same report, with prompt classifications and suggested finding priorities.</p><a href="B-jev.html">Open version B →</a></section></div>
<p>Jev status: <strong>__STATUS__</strong>. A not_run or unavailable status means no successful live comparison yet; partial means some judgments are missing.</p>
<ol><li>Give reviewers the same task, such as identifying the three findings worth investigating and explaining their evidence.</li><li>Alternate whether A or B is shown first. Record review time, useful findings, false positives, missed issues, trust, and preference.</li><li>Keep uncertain Jev suggestions visible. A low score must not hide baseline findings.</li><li>Measure analyst review time separately from software processing time. Adding Jev is additional work compared with this deterministic baseline.</li></ol>
<p><a href="feedback.csv">Feedback CSV</a> · <a href="comparison.json">Run configuration and timing</a> · <a href="baseline.json">Canonical results</a> · <a href="jev.json">Jev results</a></p><small>These reports contain metadata and evidence references. They do not embed source excerpts or make network requests.</small></html>""".replace("__STATUS__", status)
    write_new(output / "index.html", index)
    return {"directory": str(output), "index": str(output / "index.html"), **manifest}
