"""Offline report for suggested insights, separate from canonical accounting."""
from html import escape
from pathlib import Path

from .investigation import get_insights
from .util import AnalyzerError, canonical


def render_report(data):
    def text(value):
        return escape(str(value), quote=True)

    def paragraph(label, value):
        return '<p><strong>' + text(label) + '</strong> ' + text(value) + '</p>'

    def refs(record, ids):
        labels = []
        for eid in ids:
            evidence = record["evidence"].get(eid, {})
            sources = evidence.get("source_refs", [])
            label = ", ".join("line " + str(s["line"]) for s in sources) or eid
            labels.append('<span title="' + text(eid) + '">' + text(label) + '</span>')
        return '<div class="refs">Sources: ' + ' · '.join(labels) + '</div>'

    cards = []
    for record in data["insights"]:
        insight = record["insight"]
        recommendation = insight["recommendation"]
        parts = ['<article><div class="eyebrow">Proposed · ' + text(record["review"]["status"]) + '</div>',
                 '<h2>' + text(insight["title"]) + '</h2>',
                 '<div class="action">' + paragraph("Change:", recommendation["change"]),
                 paragraph("Where:", recommendation["target"]),
                 paragraph("Check afterward:", recommendation["success_measure"]) + '</div>',
                 '<h3>What the session shows</h3><ul>']
        for item in insight["observations"]:
            parts.append('<li>' + text(item["text"]) + refs(record, item["evidence_ids"]) + '</li>')
        parts.append('</ul>' + paragraph("Limits:", insight["uncertainty"]))
        parts.append('<details><summary>Reasoning and counterevidence</summary>' + paragraph("Possible explanation:", insight["hypothesis"]))
        parts.append('<h3>Evidence against the explanation</h3>')
        if insight["counterevidence"]:
            parts.append('<ul>' + ''.join('<li>' + text(x["text"]) + refs(record, x["evidence_ids"]) + '</li>' for x in insight["counterevidence"]) + '</ul>')
        else:
            parts.append('<p>No counterevidence was supplied. This does not establish that none exists.</p>')
        parts.append('<h3>Other explanations</h3><ul>' + ''.join('<li>' + text(x) + '</li>' for x in insight["alternative_explanations"]) + '</ul></details>')
        if record["review"].get("note"):
            parts.append(paragraph("Operator review:", record["review"]["note"]))
        parts.append('<details><summary>Source references, checked metrics and provenance</summary><pre>' +
                     text(canonical({k: record[k] for k in ("id", "created_at", "evidence", "checked_metrics", "validation", "review")})) +
                     '</pre>' + paragraph("Reported model / skill:", insight["provenance"]["model"] + " / " + insight["provenance"]["skill_version"]) + '</details></article>')
        cards.append(''.join(parts))
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ally investigation</title><style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f4f5ef;color:#173d35;font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{background:#173d35;color:white;padding:22px max(6vw,20px)}main{max-width:1050px;margin:auto;padding:35px 24px 70px}h1{font-size:38px;line-height:1.2}h2{font-size:25px;line-height:1.3}h3{font-size:16px;margin-bottom:8px}article{background:white;border:1px solid #dce3da;border-radius:12px;padding:28px;margin:24px 0}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:1px}.notice,.action{background:#edf2e8;border-radius:8px;padding:15px 20px}.refs,code{font:12px/1.5 ui-monospace,monospace;overflow-wrap:anywhere;color:#53645c}li{margin:10px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px;max-height:400px;overflow:auto;background:#f4f5ef;padding:12px}summary{cursor:pointer}details{margin-top:24px}p{overflow-wrap:anywhere}@media(max-width:600px){h1{font-size:30px}article{padding:20px}}
</style><header>ALLY / SESSION INVESTIGATION</header><main><h1>Session recommendations</h1>
<p class="notice">Source references and structured metrics were checked. Explanations and proposed benefits still need review.</p>''' + \
        ''.join(cards or ['<article>No supported recommendations have been saved for this analysis.</article>']) + \
        '<details><summary>Analysis and review scope</summary>' + paragraph("Analysis:", data["analysis_id"]) + \
        paragraph("Saved recommendations:", len(data["insights"])) + '</details>' + \
        '<p>This export does not automatically include transcript excerpts. Model-written summaries can still contain sensitive information.</p></main></html>'


def export_investigation(store, analysis_id, destination, format="html"):
    if format not in ("html", "json"):
        raise AnalyzerError("Investigation format must be html or json")
    path = Path(destination).expanduser().resolve()
    if path == store.db_path or path == store.objects or store.objects in path.parents:
        raise AnalyzerError("Report cannot overwrite database or source objects")
    records, offset = [], 0
    while True:
        page = get_insights(store, analysis_id, 50, offset)
        records.extend(page["items"])
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    data = {"schema_version": "1", "analysis_id": analysis_id, "insights": records,
            "canonical_analysis_included": False, "transcript_excerpts_automatically_included": False}
    content = canonical(data) + "\n" if format == "json" else render_report(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as output:
            path.chmod(0o600)
            output.write(content)
    except FileExistsError:
        raise AnalyzerError("Report destination already exists; choose a new filename")
    return {"path": str(path), "analysis_id": analysis_id, "format": format,
            "bytes": path.stat().st_size, "insights_count": len(records)}
