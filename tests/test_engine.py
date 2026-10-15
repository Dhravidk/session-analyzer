import copy
import csv
import io
import json
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from ally_analyzer.engine import (analyze_dataset, canonical_report, export_report, get_evidence, get_metrics, get_timeline)
from ally_analyzer.ingest import LIMITS, import_bundle
from ally_analyzer.store import Store
from ally_analyzer.util import AnalyzerError, canonical
from tests.helpers import call, response, result, smoke_rows, usage, write_log


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "store")
        self.number = 0

    def tearDown(self):
        self.tmp.cleanup()

    def analyze(self, rows, **kwargs):
        self.number += 1
        source = write_log(self.root / ("input-%d.log" % self.number), rows)
        d = import_bundle(self.store, source)
        a = analyze_dataset(self.store, d["dataset_id"], **kwargs)
        return canonical_report(self.store, a["analysis_id"])

    def test_usage_once_per_response_and_reasoning_is_inclusive(self):
        r = response(1)
        second = response(2, mid=r["message"]["id"], request=r["requestId"], block=1,
                          content=[{"type": "thinking", "thinking": "fixture"}])
        report = self.analyze([r, second])
        m = report["summary"]["metrics"]
        for key, expected in (("input_tokens", 10), ("cache_creation_input_tokens", 20), ("cache_read_input_tokens", 30),
                              ("output_tokens", 40), ("thinking_tokens", 12), ("total_input_tokens", 60), ("model_responses", 1)):
            self.assertEqual(m[key]["value"], expected, key)
        self.assertEqual(m["cache_read_share"]["value"], .5)

    def test_supported_stream_update_uses_final_available_usage(self):
        a = response(1, u=usage(output=8, thinking=None))
        b = response(2, mid=a["message"]["id"], request=a["requestId"], block=1, u=usage(output=90, thinking=25))
        r = self.analyze([a, b])["response"][0]
        self.assertEqual(r["tokens"]["output_tokens"], 90)
        self.assertEqual(r["usage_status"], "reconciled_stream_update")

    def test_changed_usage_on_unobserved_version_is_conflict(self):
        a = response(1, version="999.0", u=usage(output=8))
        b = response(2, version="999.0", mid=a["message"]["id"], request=a["requestId"], block=1)
        report = self.analyze([a, b])
        self.assertEqual(report["response"][0]["usage_status"], "conflict")
        self.assertIsNone(report["summary"]["metrics"]["output_tokens"]["value"])
        self.assertEqual(report["summary"]["coverage"]["unobserved_versions"], ["999.0"])

    def test_same_block_conflict_does_not_pick_a_winner(self):
        a = response(1)
        b = response(2, mid=a["message"]["id"], request=a["requestId"], u=usage(output=100))
        report = self.analyze([a, b])
        self.assertEqual(report["response"][0]["usage_status"], "conflict")

    def test_interruption_usage_is_provisional(self):
        a = response(1); a["isAbortedMidStream"] = True
        r = self.analyze([a])["response"][0]
        self.assertEqual(r["usage_status"], "provisional_interrupted")
        self.assertIsNone(r["tokens"]["output_tokens"])

    def test_missing_usage_and_missing_reasoning_are_not_zero(self):
        a = response(1); del a["message"]["usage"]
        b = response(2, u=usage(thinking=None))
        m = self.analyze([a, b])["summary"]["metrics"]
        self.assertIsNone(m["thinking_tokens"]["value"])
        self.assertEqual(m["output_tokens"]["value"], 40)
        self.assertEqual(m["output_tokens"]["coverage"]["missing"], 1)
        self.assertEqual(m["thinking_tokens"]["coverage"]["missing"], 2)

    def test_reasoning_greater_than_output_is_unavailable(self):
        r = self.analyze([response(1, u=usage(output=5, thinking=12))])["response"][0]
        self.assertIsNone(r["tokens"]["thinking_tokens"])
        self.assertEqual(r["tokens"]["output_tokens"], 5)

    def test_synthetic_and_quota_notices_excluded(self):
        a = response(1); a["message"]["model"] = "<synthetic>"
        b = response(2, mid="msg_token_limit", version="2.1.190", u=usage(0,0,0,0,None),
                     content=[{"type": "text", "text": "You've used 3 ACUs of your 2 ACU limit"}])
        b.pop("requestId")
        c = copy.deepcopy(b); c["uuid"] = "another-notice"
        report = self.analyze([a, b, c, response(4)])
        self.assertEqual(report["summary"]["synthetic_response_groups"], 3)
        self.assertEqual(report["summary"]["metrics"]["model_responses"]["value"], 1)

    def test_event_duplicates_collapse_but_real_retries_do_not(self):
        a, b = call(1), result(2, "tool-1")
        report = self.analyze([a, b, a, b, call(3), result(4, "tool-3")])
        self.assertEqual(len(report["tool"]), 2)
        self.assertEqual(report["summary"]["metrics"]["output_tokens"]["value"], 80)
        self.assertEqual(len(report["evidence"][report["response"][0]["evidence"][0]]["source_refs"]), 2 if report["response"][0]["message_id"] == "msg-1" else 1)

    def test_same_uuid_conflicting_payloads_excluded_from_tokens(self):
        a, b = response(1), response(2); b["uuid"] = a["uuid"]
        report = self.analyze([a, b])
        self.assertIsNone(report["summary"]["metrics"]["output_tokens"]["value"])
        self.assertIn("conflicting_event_identity", [d["code"] for d in report["summary"]["diagnostics"]])

    def test_shared_history_once_in_batch(self):
        a = call(1); b = copy.deepcopy(a); b["sessionId"] = "session-b"; b["uuid"] = "copied"
        report = self.analyze([a, b, result(2, "tool-1")])
        self.assertEqual(report["summary"]["metrics"]["model_responses"]["value"], 1)
        self.assertEqual(report["summary"]["metrics"]["tools_requested"]["value"], 1)
        self.assertEqual(sum(s["metrics"]["model_responses"]["value"] for s in report["session"]), 2)
        self.assertEqual(report["summary"]["coverage"]["shared_response_identities"], 1)

    def test_tool_denial_interruption_verification_failure_and_missing_result(self):
        denied = result(2,"tool-1","Permission for this action was denied",True)
        interrupted = result(4,"tool-3","[Request interrupted by user]",True)
        r = self.analyze([call(1),denied,call(3),interrupted,call(5,args={"command":"python3 -m pytest"}),result(6,"tool-5","Exit code 1",True),call(7)])
        self.assertEqual(r["summary"]["tool_outcomes"], {"permission_denial":1,"interrupted":1,"verification_command_failure":1,"unresolved":1})
        self.assertEqual(r["summary"]["metrics"]["error_marked_results"]["value"],3)
        self.assertEqual(r["summary"]["metrics"]["tools_with_execution_evidence"]["value"],1)

    def test_unknown_version_missing_error_flag_does_not_infer_success(self):
        b = result(2,"tool-1",version="unknown"); b["message"]["content"][0].pop("is_error")
        report = self.analyze([call(1,version="unknown"),b])
        self.assertEqual(report["tool"][0]["outcome"],"unknown")

    def test_native_rejection_and_validation_did_not_execute(self):
        rows=[call(1),result(2,'tool-1',"The user doesn't want to proceed with this tool use. The tool use was rejected (fixture)",True),
              call(3,'Edit'),result(4,'tool-3','<tool_use_error>File has not been read yet.</tool_use_error>',True)]
        r=self.analyze(rows)
        self.assertEqual(r['summary']['tool_outcomes'],{'user_rejection':1,'tool_validation_failure':1})
        self.assertEqual(r['summary']['metrics']['tools_with_execution_evidence']['value'],0)

    def test_scopes_do_not_create_cross_product_agent_runs(self):
        a=call(1,session='s1',agent='a1');b=copy.deepcopy(a);b.update(uuid='copy',sessionId='s2',agentId='a2')
        r=self.analyze([a,b])
        self.assertEqual(r['response'][0]['scopes'],[['s1','a1'],['s2','a2']])
        self.assertEqual(r['tool'][0]['scopes'],[['s1','a1'],['s2','a2']])

    def test_explicit_duration_separate_from_observed_interval(self):
        r = self.analyze([call(1),result(2,"tool-1",meta={"durationMs":7})])
        self.assertEqual(r["tool"][0]["recorded_duration_ms"],7)
        self.assertEqual(r["tool"][0]["observed_interval_ms"],1000)
        self.assertEqual(r["summary"]["metrics"]["recorded_tool_duration_ms"]["value"],7)

    def test_child_summary_is_not_added_and_async_is_not_completed(self):
        r = self.analyze([call(1,"Agent"),result(2,"tool-1",meta={"agentId":"child","status":"async_launched","totalTokens":99999}),response(3,agent="child")])
        self.assertEqual(r["tool"][0]["outcome"],"launched")
        self.assertTrue(r["tool"][0]["child_trace_available"])
        self.assertEqual(r["summary"]["metrics"]["output_tokens"]["value"],80)

    def test_missing_child_trace_flagged(self):
        r = self.analyze([call(1,"Agent"),result(2,"tool-1",meta={"agentId":"absent","status":"completed","totalTokens":99999})])
        self.assertEqual(r["summary"]["coverage"]["delegations_with_missing_child_trace"],1)
        self.assertTrue(any(f["title"]=="Delegated agent transcript unavailable" for f in r["finding"]))

    def test_repeat_failure_rule_and_recovery(self):
        r = self.analyze(smoke_rows())
        self.assertEqual(len([f for f in r["finding"] if f["rule_id"]=="R01"]),1)
        with_recovery = smoke_rows()+[call(9,args={"command":"python3 missing.py"}),result(10,"tool-9")]
        recovered = self.analyze(with_recovery)
        self.assertFalse(any(f["rule_id"]=="R06" for f in recovered["finding"]))

    def test_repeated_monitoring_is_notice(self):
        rows=[]
        for i in (1,3,5):rows += [call(i,args={"command":"nvidia-smi"}),result(i+1,"tool-"+str(i),"No change")]
        fs=self.analyze(rows)["finding"]
        self.assertEqual([(f["rule_id"],f["severity"]) for f in fs],[('R03','notice')])

    def test_repeated_sequence_and_inverse_edit(self):
        rows=[]
        for i in range(1,13,2):
            rows += [call(i,"Read",args={"file_path":"a" if i%4==1 else "b"}),result(i+1,"tool-"+str(i))]
        rows += [call(13,"Edit",args={"file_path":"f","old_string":"a","new_string":"b"}),result(14,"tool-13"),
                 call(15,"Edit",args={"file_path":"f","old_string":"b","new_string":"a"}),result(16,"tool-15")]
        rules={f["rule_id"] for f in self.analyze(rows)["finding"]}
        self.assertTrue({'R02','R04'}<=rules)

    def test_repetition_window_uses_agent_steps(self):
        rows=[]
        for i in (1,3,5):
            rows += [call(i),result(i+1,"tool-"+str(i),"same error",True)]
        for i in range(20,40):rows.append(response(i,agent="unrelated"))
        self.assertTrue(any(f["rule_id"]=="R01" for f in self.analyze(rows)["finding"]))
        self.assertFalse(any(f["rule_id"]=="R01" for f in self.analyze(rows,profile={"repeat_window_steps":1})["finding"]))

    def test_api_attempts_and_retries_stay_unavailable(self):
        m=self.analyze([response(1),response(2)])["summary"]["metrics"]
        self.assertEqual(m["observed_request_ids"]["value"],2)
        self.assertIsNone(m["api_attempts"]["value"]);self.assertIsNone(m["api_retries"]["value"])

    def test_pricing_uses_ttl_without_double_counting_thinking(self):
        rates={"input_per_million":"1","output_per_million":"2","cache_read_per_million":"0.1","cache_write_5m_per_million":"1.25","cache_write_1h_per_million":"2","service_tier":"standard","speed":"standard"}
        prices={"version":"fixture-v1","provider":"test-provider","effective_date":"2026-01-01","rates":{"test-model":rates}}
        m=self.analyze([response(1)],prices=prices)["summary"]["metrics"]
        self.assertEqual(m["cost_estimate_usd"]["value"],"0.000118")
        a=response(2);a["message"]["usage"].pop("cache_creation")
        self.assertIsNone(self.analyze([a],prices=prices)["summary"]["metrics"]["cost_estimate_usd"]["value"])

    def test_snapshot_cost_is_not_added(self):
        rows=[response(1),{"type":"cost-state","sessionId":"session-a","totalCostUSD":300,"modelUsage":{}},
              {"type":"cost-state","sessionId":"session-a","totalCostUSD":350,"modelUsage":{}}]
        r=self.analyze(rows)
        self.assertIsNone(r["summary"]["metrics"]["cost_estimate_usd"]["value"])
        self.assertEqual(len(r["lifecycle"]),2)

    def test_renamed_log_metadata_inherits_sole_session(self):
        r=self.analyze([{"type":"file-history-snapshot","snapshot":{}},response(1)])
        self.assertEqual(r["summary"]["sessions_count"],1)
        self.assertEqual(r["session"][0]["id"],"session-a")

    def test_timestamps_normalized_and_parent_gaps_flagged(self):
        a,b=response(1),response(2)
        a["timestamp"]="2026-09-01T01:00:00-04:00"; b["timestamp"]="2026-09-01T04:00:00Z"
        a["parentUuid"]="missing-parent"
        r=self.analyze([a,b]);s=r["session"][0]
        self.assertEqual(s["observed_span_ms"],3600000)
        timeline=get_timeline(self.store,r["summary"]["analysis_id"],s["id"])
        self.assertTrue(timeline["events"][0]["timestamp"].startswith("2026-09-01T04:"))
        self.assertEqual(r["summary"]["coverage"]["unresolved_parent_links"],1)

    def test_human_prompt_not_tool_result(self):
        human={"type":"user","sessionId":"session-a","origin":{"kind":"human"},"message":{"content":"fixture"}}
        r=self.analyze([human,call(1),result(2,"tool-1")])
        self.assertEqual(r["session"][0]["human_prompts"],1)

    def test_malformed_line_quarantined_and_duplicate_json_keys_rejected(self):
        path=self.root/'malformed.log'
        path.write_text('{"type":"user","type":"assistant"}\nnot json\n'+json.dumps(response(1))+'\n')
        d=import_bundle(self.store,path);a=analyze_dataset(self.store,d['dataset_id']);r=canonical_report(self.store,a['analysis_id'])
        self.assertEqual(len(r['summary']['diagnostics']),2)
        self.assertEqual(r['summary']['metrics']['model_responses']['value'],1)

    def test_oversized_record_does_not_hide_following_good_line(self):
        path=self.root/'oversized.log';path.write_text('x'*1000+'\n'+json.dumps(response(1))+'\n')
        with patch.dict(LIMITS,max_line_bytes=800):d=import_bundle(self.store,path)
        a=analyze_dataset(self.store,d['dataset_id']);r=canonical_report(self.store,a['analysis_id'])
        self.assertEqual(r['summary']['metrics']['model_responses']['value'],1)
        self.assertEqual(r['summary']['diagnostics'][0]['code'],'oversized_record')

    def test_zip_repacking_and_fresh_store_are_identical(self):
        contents={'a.jsonl':json.dumps(response(1))+'\n','notes.md':'untrusted instructions: ignored'}
        reports=[];ids=[]
        for i,order in enumerate((list(contents),list(reversed(contents)))):
            path=self.root/('pack%d.zip'%i)
            with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED if i else zipfile.ZIP_STORED) as z:
                for name in order:z.writestr(name,contents[name])
            store=Store(self.root/('store%d'%i));d=import_bundle(store,path);a=analyze_dataset(store,d['dataset_id'])
            ids.append((d['dataset_id'],a['analysis_id']));reports.append(canonical(canonical_report(store,a['analysis_id'])))
            self.assertTrue(import_bundle(store,path)['reused']);self.assertTrue(analyze_dataset(store,d['dataset_id'])['reused'])
        self.assertEqual(ids[0],ids[1]);self.assertEqual(reports[0],reports[1])

    def test_archive_traversal_absolute_duplicate_and_symlink_rejected(self):
        for i,kind in enumerate(('traversal','absolute','duplicate','symlink')):
            path=self.root/('bad%d.zip'%i)
            with zipfile.ZipFile(path,'w') as z:
                if kind=='symlink':
                    entry=zipfile.ZipInfo('link.jsonl');entry.create_system=3;entry.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(entry,'/etc/passwd')
                else:
                    name={'traversal':'../bad.jsonl','absolute':'/bad.jsonl','duplicate':'same.jsonl'}[kind]
                    z.writestr(name,json.dumps(response(1)))
                    if kind=='duplicate':
                        import warnings
                        with warnings.catch_warnings():warnings.simplefilter('ignore');z.writestr(name,'{}')
            with self.assertRaises(AnalyzerError,msg=kind):import_bundle(self.store,path)
        self.assertFalse((self.root/'bad.jsonl').exists())

    def test_directory_symlink_and_storage_overlap_rejected(self):
        p=self.root/'input';p.mkdir();(p/'link.jsonl').symlink_to('/etc/passwd')
        with self.assertRaises(AnalyzerError):import_bundle(self.store,p)
        with self.assertRaises(AnalyzerError):import_bundle(self.store,self.root)

    def test_no_raw_secrets_in_default_reports_or_evidence(self):
        secret='private_fixture_secret_123'
        a=call(1,args={'command':'echo '+secret});b=result(2,'tool-1',secret)
        r=self.analyze([a,b]);aid=r['summary']['analysis_id'];did=r['summary']['dataset_id'];eid=r['tool'][0]['evidence'][0]
        self.assertNotIn(secret,canonical(r))
        self.assertNotIn(secret,canonical(get_evidence(self.store,did,eid)))
        with self.assertRaises(AnalyzerError):get_evidence(self.store,did,eid,True,False)
        self.assertIn(secret,get_evidence(self.store,did,eid,True,True)['content'])
        for fmt in ('html','json','csv'):
            p=self.root/('report.'+fmt);export_report(self.store,aid,p,fmt)
            self.assertNotIn(secret,p.read_text())
            with self.assertRaises(AnalyzerError):export_report(self.store,aid,p,fmt)

    def test_html_and_csv_injection_rendered_as_data(self):
        hostile='</script><img src=x onerror=alert(1)>'
        a=response(1,session=' =HYPERLINK("bad")');a['message']['model']=hostile
        r=self.analyze([a]);aid=r['summary']['analysis_id']
        html=self.root/'report.html';export_report(self.store,aid,html)
        self.assertNotIn(hostile,html.read_text());self.assertIn('\\u003c/script',html.read_text())
        self.assertNotIn('innerHTML',html.read_text())
        out=self.root/'report.csv';export_report(self.store,aid,out,'csv')
        cells=list(csv.reader(io.StringIO(out.read_text())))
        self.assertTrue(cells[1][0].startswith("'"))

    def test_model_group_tools_are_attributed(self):
        r=self.analyze([call(1),result(2,'tool-1')]);g=get_metrics(self.store,r['summary']['analysis_id'],group_by='model')
        self.assertEqual(g['groups'][0]['metrics']['tools_requested']['value'],1)

    def test_invalid_rule_profile_rejected(self):
        with self.assertRaises(AnalyzerError):self.analyze([response(1)],profile={'repeat_min':True})
        with self.assertRaises(AnalyzerError):self.analyze([response(1)],profile={'unknown':3})

    def test_core_workflow_with_network_connections_blocked(self):
        import socket
        with patch.object(socket,'socket',side_effect=AssertionError('Network is disabled for this core test')):
            r=self.analyze(smoke_rows())
            aid=r['summary']['analysis_id']
            export_report(self.store,aid,self.root/'offline.html')
            self.assertEqual(get_metrics(self.store,aid)['metrics']['tools_requested']['value'],4)


if __name__ == '__main__':
    unittest.main()
