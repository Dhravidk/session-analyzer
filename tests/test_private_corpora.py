"""Opt-in regressions. Private sources are never copied into the repository."""
import hashlib
import os
import tempfile
import unittest

from ally_analyzer.engine import analyze_dataset
from ally_analyzer.ingest import import_bundle
from ally_analyzer.store import Store


class PrivateCorpusTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('ALLY_TEST_SESSION'), 'Set ALLY_TEST_SESSION to the supplied session.log')
    def test_ally_export(self):
        path=os.environ['ALLY_TEST_SESSION']
        with open(path,'rb') as f:self.assertEqual(hashlib.sha256(f.read()).hexdigest(),'a3c03a876eebca9bed36ea75a0c601534440370f3c0c1f6fd0971a144fce8741')
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);d=import_bundle(s,path,namespace='ally-regression');a=analyze_dataset(s,d['dataset_id']);summary=s.analysis(a['analysis_id'])['summary'];m=summary['metrics']
            self.assertEqual(summary['sessions_count'],1)
            self.assertEqual(summary['synthetic_response_groups'],3)
            self.assertEqual(m['model_responses']['value'],806)
            self.assertEqual(m['tools_requested']['value'],773)
            self.assertEqual(m['tool_results']['value'],773)
            self.assertEqual(m['error_marked_results']['value'],15)
            self.assertEqual(summary['tool_outcomes'],{'success':745,'launched':13,'execution_failure':6,'tool_validation_failure':5,'user_rejection':4})
            for k,v in {'input_tokens':1612,'cache_creation_input_tokens':14699387,'cache_read_input_tokens':386423782,'output_tokens':517079}.items():
                self.assertEqual(m[k]['value'],v,k);self.assertEqual(m[k]['coverage']['known'],806)
            self.assertIsNone(m['thinking_tokens']['value'])
            self.assertEqual(summary['coverage']['delegations_with_missing_child_trace'],16)

    @unittest.skipUnless(os.environ.get('ALLY_TEST_ARCHIVE'), 'Set ALLY_TEST_ARCHIVE to the example ZIP')
    def test_example_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp);d=import_bundle(s,os.environ['ALLY_TEST_ARCHIVE']);a=analyze_dataset(s,d['dataset_id']);summary=s.analysis(a['analysis_id'])['summary'];m=summary['metrics']
            self.assertEqual(summary['sessions_count'],33)
            self.assertEqual(summary['response_groups_including_synthetic'],3291)
            self.assertEqual(summary['synthetic_response_groups'],5)
            self.assertEqual(m['tools_requested']['value'],2597)
            self.assertEqual(m['error_marked_results']['value'],79)
            self.assertEqual(m['output_tokens']['value'],2332421)
            self.assertEqual(m['output_tokens']['coverage']['missing'],1)
            self.assertEqual(m['thinking_tokens']['value'],706683)
            self.assertTrue(any(d['code']=='malformed_record' for d in summary['diagnostics']))


if __name__=='__main__':unittest.main()
