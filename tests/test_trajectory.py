import hashlib
import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ally_analyzer.engine import analyze_dataset, canonical_report
from ally_analyzer.ingest import import_bundle
from ally_analyzer.investigation import get_investigation_context
from ally_analyzer.mcp import Protocol
from ally_analyzer.service import Service
from ally_analyzer.store import Store
from ally_analyzer.trajectory import read_trajectory_event, search_trajectory, trajectory_text
from ally_analyzer.util import AnalyzerError, canonical, strict_json
from tests.helpers import call, response, result, write_log

ROOT = Path(__file__).resolve().parent.parent


class TrajectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "store")
        self.body = "Opening request.\n" + "Ordinary context café 🧭\n" * 800 + "Late evidence: needle [x].\nEnd."
        self.rows = [response(0), call(1, name="Write", args={"file_path": "/synthetic/report.md", "content": self.body}),
                     result(2, "tool-1", "File created."),
                     response(3, agent="child-a", content=[{"type": "text", "text": "needle [x]. child only"}]),
                     response(4, session="session-b", content=[{"type": "text", "text": "needle [x]. other session"}]),
                     response(5), response(6, content=[{"type": "text", "text": "Later recovery, needle [x]."}])]
        self.source = write_log(self.root / "fixture.log", self.rows)
        self.dataset = import_bundle(self.store, self.source)["dataset_id"]
        self.aid = analyze_dataset(self.store, self.dataset)["analysis_id"]
        with self.store.connect() as db:
            self.events = {strict_json(r["raw"])["uuid"]: r["id"] for r in db.execute("SELECT id,raw FROM events WHERE dataset_id=?", (self.dataset,))}

    def tearDown(self):
        self.temp.cleanup()

    def read(self, i=1, **kwargs):
        return read_trajectory_event(self.store, self.aid, self.events["event-" + str(i)], allow_content=True, **kwargs)

    def search(self, **kwargs):
        return search_trajectory(self.store, self.aid, "needle [x].", allow_content=True, **kwargs)

    def test_full_long_tool_input_is_recoverable_without_gaps(self):
        pages, cursor, fingerprint = [], 0, None
        while cursor is not None:
            page = self.read(start_char=cursor, max_chars=1024, expected_text_sha256=fingerprint)
            self.assertEqual(page["start_char"], cursor)
            self.assertEqual(page["end_char"] - cursor, len(page["text"]))
            self.assertEqual(page["has_text_before"], cursor > 0)
            self.assertEqual(page["has_text_after"], page["next_start_char"] is not None)
            self.assertLessEqual(len(page["text"]), 1024)
            pages.append(page["text"])
            cursor, fingerprint = page["next_start_char"], page["text_sha256"]
        expected, _ = trajectory_text(self.rows[1])
        self.assertEqual("".join(pages), expected)
        self.assertEqual(fingerprint, hashlib.sha256(expected.encode("utf-8")).hexdigest())
        self.assertEqual(json.loads(expected.split("Input: ", 1)[1])["content"], self.body)
        self.assertGreater(len(pages), 12)
        self.assertEqual(self.read(start_char=len(expected))["text"], "")

    def test_partial_empty_search_is_not_absence_and_tail_hit_can_be_read(self):
        first = self.search(max_scan=1)
        self.assertEqual(first["matches"], [])
        self.assertFalse(first["scan"]["reached_end_of_scope"])
        self.assertEqual(first["scan"]["next_scan_offset"], 1)
        next_page = self.search(max_scan=1, scan_offset=1)
        match = next_page["matches"][0]
        self.assertEqual(match["event_id"], self.events["event-1"])
        self.assertGreater(match["match_start_char"], 12000)
        page = self.read(start_char=match["match_start_char"], max_chars=100,
                         expected_text_sha256=match["text_sha256"])
        self.assertTrue(page["text"].startswith("needle [x]."))
        self.assertEqual(page["evidence"]["source_refs"][0]["line"], 2)

    def test_search_hit_limit_paginates_and_filters_sessions_and_agents(self):
        ids, cursor = [], 0
        while cursor is not None:
            page = self.search(limit=1, scan_offset=cursor)
            ids.extend(m["event_id"] for m in page["matches"])
            cursor = page["scan"]["next_scan_offset"]
        self.assertEqual(ids, [self.events["event-" + str(i)] for i in (1, 3, 4, 6)])
        filtered = self.search(session_id="session-a", agent_id="main")
        self.assertEqual([m["event_id"] for m in filtered["matches"]], [self.events["event-1"], self.events["event-6"]])
        self.assertTrue(filtered["scan"]["entire_scope_scanned_in_this_call"])
        self.assertEqual(self.search(session_id="unknown")["scan"]["scope_events"], 0)

    def test_navigation_is_scoped_and_preview_advertises_rereading(self):
        nav = self.read(2)["navigation"]
        self.assertEqual(nav["previous_event_id"], self.events["event-1"])
        self.assertEqual(nav["next_event_id"], self.events["event-5"])
        self.assertIsNone(self.read(3)["navigation"]["next_event_id"])
        preview = get_investigation_context(self.store, self.aid, self.events["event-1"], before=0,
                                            after=0, include_content=True, allow_content=True)
        self.assertNotIn("needle", preview["events"][0]["excerpt"])
        self.assertEqual(preview["events"][0]["reread"]["tool"], "read_trajectory_event")
        self.assertTrue(any("tool input fields" in note for note in preview["limitations"]))

    def test_projection_retains_questions_and_attachments_but_discloses_omissions(self):
        record = {"environment": {"X": "top-env-only"}, "lastPrompt": "A retained last prompt",
                  "data": {"message": {"content": [{"type": "text", "text": "nested progress text"},
                                                       {"type": "thinking", "thinking": "progress-thinking-only"}]}},
                  "attachment": {"type": "queued_command", "prompt": "queued request"},
                  "message": {"content": [
                      {"type": "thinking", "thinking": "hidden-thinking-only"},
                      {"type": "image", "source": {"data": "image-data-only"}},
                      {"type": "tool_use", "name": "AskUserQuestion", "input": {
                          "questions": [{"question": "Which command?", "options": [{"label": "Run checks"}]}],
                          "api_key": "secret-value-only", "environment": {"X": "nested-env-only"},
                          "content": 'API_KEY="quoted secret" person@example.com /Users/alice/repo'}},
                      {"type": "tool_result", "content": [{"type": "text", "text": "visible result"},
                                                               {"type": "image", "data": "nested-image-only"}]}]}}
        text, disclosure = trajectory_text(record)
        for retained in ("Which command?", "Run checks", "visible result", "queued request", "A retained last prompt", "nested progress text"):
            self.assertIn(retained, text)
        for excluded in ("top-env-only", "hidden-thinking-only", "image-data-only", "secret-value-only", "nested-env-only",
                         "quoted secret", "person@example.com", "/Users/alice", "nested-image-only", "progress-thinking-only"):
            self.assertNotIn(excluded, text)
        self.assertIn("thinking_payload_excluded", disclosure["omitted_categories"])
        self.assertGreater(disclosure["redaction_matches"], 0)

    def test_policy_bounds_wrong_fingerprint_and_foreign_analysis(self):
        service = Service(self.store)
        try:
            for name, args in (("read_trajectory_event", {"event_id": self.events["event-1"]}),
                               ("search_trajectory", {"query": "needle"})):
                with self.assertRaises(AnalyzerError):
                    service.call(name, dict(analysis_id=self.aid, **args))
        finally:
            service.close()
        for args in ({"start_char": -1}, {"start_char": 1000000}, {"max_chars": 12001},
                     {"max_chars": True}, {"expected_text_sha256": "0" * 64}):
            with self.assertRaises(AnalyzerError):
                self.read(**args)
        for args in ({"limit": 51}, {"scan_offset": -1}, {"max_scan": 5001}):
            with self.assertRaises(AnalyzerError):
                self.search(**args)
        with self.assertRaises(AnalyzerError):
            search_trajectory(self.store, self.aid, " ", allow_content=True)
        other = import_bundle(self.store, write_log(self.root / "other.log", [response(90)]))["dataset_id"]
        other_aid = analyze_dataset(self.store, other)["analysis_id"]
        with self.assertRaises(AnalyzerError):
            read_trajectory_event(self.store, other_aid, self.events["event-1"], allow_content=True)

    def test_rereading_needs_no_network_and_preserves_canonical_data_and_source(self):
        before, source = canonical(canonical_report(self.store, self.aid)), self.source.read_bytes()
        with self.store.connect() as db:
            raw = list(db.execute("SELECT id,raw FROM events ORDER BY id"))
        with patch.object(socket, "socket", side_effect=AssertionError("Network must not be used")):
            self.read(); self.search()
        self.assertEqual(before, canonical(canonical_report(self.store, self.aid)))
        self.assertEqual(source, self.source.read_bytes())
        with self.store.connect() as db:
            self.assertEqual(raw, list(db.execute("SELECT id,raw FROM events ORDER BY id")))

    def test_cli_and_mcp_return_same_pages(self):
        service = Service(self.store, allow_content=True)
        protocol = Protocol(service)
        try:
            protocol.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
            protocol.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
            cases = [("read_trajectory_event", {"event_id": self.events["event-1"], "start_char": 12000, "max_chars": 90},
                      ["trajectory-read", self.aid, self.events["event-1"], "--start-char", "12000", "--max-chars", "90"]),
                     ("search_trajectory", {"query": "needle [x].", "max_scan": 2},
                      ["trajectory-search", self.aid, "needle [x].", "--max-scan", "2"])]
            for name, args, cli_args in cases:
                result = protocol.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                          "params": {"name": name, "arguments": dict(analysis_id=self.aid, **args)}})["result"]
                self.assertFalse(result["isError"])
                cli = subprocess.run([sys.executable, "-m", "ally_analyzer", "--data-dir", str(self.store.root), *cli_args],
                                     cwd=ROOT, capture_output=True, text=True, timeout=10)
                self.assertEqual(cli.returncode, 0, cli.stderr)
                self.assertEqual(json.loads(cli.stdout), result["structuredContent"])
            invalid = protocol.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                "name": "read_trajectory_event", "arguments": {"analysis_id": self.aid, "event_id": self.events["event-1"],
                                                               "expected_text_sha256": "too-short"}}})
            self.assertTrue(invalid["result"]["isError"])
        finally:
            service.close()


if __name__ == "__main__":
    unittest.main()
