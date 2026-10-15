import copy
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "variants" / "jev"))

from ally_analyzer.engine import analyze_dataset, canonical_report, get_metrics
from ally_analyzer.ingest import import_bundle
from ally_analyzer.store import Store
from ally_analyzer.util import AnalyzerError, canonical
from ally_analyzer_jev.client import Client, JevError, validate_response
from ally_analyzer_jev.config import config
from ally_analyzer_jev.evidence import prepare, preview
from ally_analyzer_jev.mcp import Protocol, Service
from ally_analyzer_jev.pipeline import interpret
from ally_analyzer_jev.report import compare


def answer(payload):
    """Contract fixture only. These judgments are deliberately NOT model outputs."""
    answers = {}
    for name, q in payload["questions"].items():
        if q["type"] == "choice":
            selected = "correction" if name == "prompt_kind" else "sufficient"
            answers[name] = {"type": "choice", "choice": selected, "confidence": 1,
                             "probabilities": {k: int(k == selected) for k in q["criteria"]}}
        else:
            answers[name] = {"type": "score", "score": 2, "confidence": 1,
                "legend": {str(i): v for i, v in enumerate(q["criteria"])},
                "probabilities": {str(i): int(i == 2) for i in range(len(q["criteria"]))}}
    return {"model": payload["model"], "answers": answers, "usage": {"input_tokens": 100, "output_tokens": 10}}


class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.store = Store(self.path / "store")
        self.log = self.path / "source" / "sample.jsonl"
        self.log.parent.mkdir()
        lines = (ROOT / "tests" / "fixtures" / "smoke.jsonl").read_text().splitlines()
        lines.append(json.dumps({"type": "user", "uuid": "prompt-fixture", "sessionId": "session-a",
            "timestamp": "2026-09-01T12:00:09Z", "version": "2.1.294",
            "message": {"role": "user", "content": [{"type": "text", "text": "No, preserve null. API_KEY=super-secret-fixture alice@example.com /Users/alice/private"}]}}))
        self.log.write_text("\n".join(lines) + "\n")
        dataset = import_bundle(self.store, self.log)
        self.aid = analyze_dataset(self.store, dataset["dataset_id"])["analysis_id"]
        self.settings = config({"content_mode": "excerpts", "workers": 1})
        self.calls = []
        def transport(payload):
            self.calls.append(payload)
            return answer(payload)
        self.client = Client(self.settings, api_key="fixture-not-a-key", transport=transport)

    def test_core_is_byte_identical_and_usage_stays_separate(self):
        before = canonical(canonical_report(self.store, self.aid))
        metrics = get_metrics(self.store, self.aid)
        run = interpret(self.store, self.aid, self.settings, client=self.client)
        self.assertEqual(before, canonical(canonical_report(self.store, self.aid)))
        self.assertEqual(metrics, get_metrics(self.store, self.aid))
        self.assertEqual(run["status"], "complete")
        self.assertTrue(any(a["kind"] == "prompt" for a in run["annotations"]))
        self.assertEqual(run["operational"]["usage_from_successful_requests"]["input_tokens"], 100 * len(self.calls))
        self.assertNotIn("super-secret-fixture", canonical(self.calls))
        self.assertNotIn("alice@example.com", canonical(self.calls))
        self.assertNotIn("/Users/alice", canonical(self.calls))
        self.assertNotIn("preserve null", canonical(run))
        self.assertTrue(all(a.get("sender_origin") != "recorded_human" for a in run["annotations"]))

    def test_metadata_and_preview_never_send_content(self):
        plan = prepare(self.store, self.aid)
        self.assertEqual(plan["coverage"]["prompt_selected"], 0)
        self.assertNotIn("missing.py", canonical(plan))
        self.assertNotIn("super-secret-fixture", canonical(plan))
        self.assertEqual(preview(plan)["network_requests_made"], 0)

    def test_request_caps_and_evidence_references_match_supplied_context(self):
        plan = prepare(self.store,self.aid,{**self.settings,"max_findings":1,"max_prompts":0,"context_events":2})
        self.assertEqual(len(plan["requests"]),1)
        r=plan["requests"][0]
        self.assertEqual(set(r["evidence"]),{x["event_id"] for x in r["payload"]["state"]["context"]})
        self.assertLessEqual(len(r["evidence"]),2)
        self.assertLessEqual(len(canonical(r["payload"]).encode()),30000)
        self.assertEqual(plan["coverage"]["finding_candidates"],2)
        run=interpret(self.store,self.aid,{**self.settings,"max_findings":0,"max_prompts":0},client=self.client)
        self.assertEqual(run["status"],"no_candidates")
        self.assertEqual(self.calls,[])

    def test_corrupt_cache_does_not_become_a_valid_decision(self):
        first=interpret(self.store,self.aid,self.settings,client=self.client)
        request_id=first["annotations"][0]["request_id"]
        cache=self.store.root/'jev'/'cache'/(request_id+'.json')
        cache.write_text('{"model":"untrusted", "answers":{}}')
        before=len(self.calls)
        second=interpret(self.store,self.aid,self.settings,client=self.client)
        self.assertEqual(len(self.calls),before+1)
        self.assertEqual(second["operational"]["cache_hits"],before-1)

    def test_cached_answers_are_free_this_run_and_config_changes_invalidate(self):
        first = interpret(self.store, self.aid, self.settings, client=self.client)
        n = len(self.calls)
        second = interpret(self.store, self.aid, self.settings, client=self.client)
        self.assertEqual(n, len(self.calls))
        self.assertEqual(second["operational"]["cache_hits"], n)
        self.assertEqual(second["operational"]["usage_from_successful_requests"]["input_tokens"], 0)
        interpret(self.store, self.aid, {**self.settings, "content_mode": "metadata"}, client=self.client)
        self.assertGreater(len(self.calls), n)
        self.assertNotEqual(first["run_id"], second["run_id"])

    def test_failure_keeps_baseline_and_stops_after_billing(self):
        def fail(payload):
            raise urllib.error.HTTPError("https://api.typesafe.ai", 402, "private error body", {}, None)
        client = Client(self.settings, "fake", transport=fail)
        before = canonical(canonical_report(self.store, self.aid))
        run = interpret(self.store, self.aid, self.settings, client=client)
        self.assertEqual(run["status"], "unavailable")
        self.assertEqual(run["operational"]["http_attempts"], 1)
        self.assertEqual(run["annotations"][0]["error"]["code"], "billing")
        self.assertNotIn("private error body", canonical(run))
        self.assertEqual(before, canonical(canonical_report(self.store, self.aid)))

    def test_missing_credentials_is_visible_not_fake_success(self):
        run = interpret(self.store, self.aid, self.settings, client=Client(self.settings, api_key=""))
        self.assertEqual(run["status"], "unavailable")
        self.assertEqual(run["operational"]["http_attempts"], 0)
        self.assertEqual(run["annotations"][0]["error"]["code"], "missing_api_key")

    def test_unknown_and_low_confidence_labels_remain_visible(self):
        def uncertain(payload):
            r = answer(payload)
            if "prompt_kind" in r["answers"]:
                p = r["answers"]["prompt_kind"]
                p["choice"] = "insufficient_evidence"
                p["probabilities"] = {k: int(k == p["choice"]) for k in p["probabilities"]}
            else:
                r["answers"]["review_priority"]["confidence"] = 0.1
            return r
        run = interpret(self.store, self.aid, self.settings, client=Client(self.settings,"fake",transport=uncertain))
        self.assertTrue(all(a["disposition"] == "review" for a in run["annotations"]))

    def test_response_contract_rejects_unknown_labels_nan_and_model_drift(self):
        payload = next(r["payload"] for r in prepare(self.store,self.aid,self.settings)["requests"] if r["kind"] == "prompt")
        for mutate in (lambda r: r["answers"]["prompt_kind"].update(choice="invented"),
                       lambda r: r["answers"]["prompt_kind"].update(confidence=float("nan")),
                       lambda r: r.update(model="jev-latest"),
                       lambda r: r["usage"].update(input_tokens=True),
                       lambda r: r["answers"].update(unasked={"type":"noul","noul":1})):
            r = answer(payload); mutate(r)
            with self.assertRaises(JevError):
                validate_response(r,payload)

    def test_retries_respect_rate_limit_without_repeating_timeouts(self):
        payload = prepare(self.store,self.aid,self.settings)["requests"][0]["payload"]
        calls, sleeps = [], []
        def rate_limit(p):
            calls.append(p)
            if len(calls) == 1:
                raise urllib.error.HTTPError("https://api.typesafe.ai",429,"limited",{"Retry-After":"2"},None)
            return answer(p)
        result = Client(self.settings,"fake",transport=rate_limit,sleep=sleeps.append).evaluate(payload)
        self.assertEqual(result["attempts"],2); self.assertEqual(sleeps,[2])
        def timeout(p): raise TimeoutError("private request text")
        with self.assertRaises(JevError) as error:
            Client(self.settings,"fake",transport=timeout).evaluate(payload)
        self.assertEqual(error.exception.attempts,1)
        self.assertNotIn("private request text",str(error.exception))

    def test_preview_and_live_reports_have_identical_canonical_payloads(self):
        for live in (False,True):
            folder = self.path / ("live" if live else "preview")
            result = compare(self.store,self.log,folder,self.settings,live,client=self.client)
            a = (folder / "A-baseline.html").read_text()
            b = (folder / "B-jev.html").read_text()
            pattern = r'<script type="application/json" id="analysis-data">(.*?)</script>'
            self.assertEqual(re.search(pattern,a,re.S).group(1),re.search(pattern,b,re.S).group(1))
            self.assertEqual(result["canonical_sha256_A"],result["canonical_sha256_B"])
            self.assertNotIn("super-secret-fixture",b)
            self.assertNotIn('id="jev-data"',a)
            self.assertIn('id="jev-data"',b)
            self.assertNotIn('__RUNTIME_JSON__',b)
            self.assertEqual(result["jev_status"],"complete" if live else "not_run")
            with self.assertRaises(AnalyzerError):
                compare(self.store,self.log,folder,self.settings,live,client=self.client)

    def test_mcp_keeps_base_tools_and_disables_remote_calls_by_default(self):
        from ally_analyzer.mcp import TOOLS
        service = Service(self.store,enabled=False,settings=self.settings)
        self.addCleanup(service.close)
        protocol = Protocol(service)
        protocol.handle({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}})
        protocol.handle({"jsonrpc":"2.0","method":"notifications/initialized"})
        result = protocol.handle({"jsonrpc":"2.0","id":2,"method":"tools/list"})["result"]
        self.assertEqual(result["tools"][:len(TOOLS)],TOOLS)
        denied = protocol.handle({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"jev_interpret","arguments":{"analysis_id":self.aid}}})
        self.assertTrue(denied["result"]["isError"])
        metrics = service.call("get_metrics",{"analysis_id":self.aid})
        self.assertEqual(metrics,get_metrics(self.store,self.aid))

    def test_cli_preview_has_no_network_and_bad_configuration_fails(self):
        out = self.path / "cli-preview"
        process = subprocess.run([sys.executable,str(ROOT/"variants/jev/run.py"),"--data-dir",str(self.store.root),
            "compare",str(self.log),"--output",str(out)],capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertEqual(json.loads(process.stdout)["jev_status"],"not_run")
        for c in ({"model":"jev-latest"},{"workers":True},{"min_probability":float("nan")},{"unknown":1}):
            with self.assertRaises(AnalyzerError): config(c)


if __name__ == "__main__":
    unittest.main()
