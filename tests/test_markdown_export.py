"""Markdown must retain evidence, qualifications and exact replacement/source text."""
import copy
import json
import re
import subprocess
import sys
import unittest

from ally_analyzer.session_markdown import anchor, render_markdown, text
from ally_analyzer.session_report import export_session_investigation, report_data, render_report
from ally_analyzer.session_scope import exposure
from ally_analyzer.util import AnalyzerError
from tests import test_session_diagnostics as fixture


class MarkdownExportTests(unittest.TestCase):
    setUp = fixture.DiagnosticTests.setUp
    load = fixture.DiagnosticTests.load
    contract_version = 'single-session-v2'

    def test_partial_prose_metrics_and_sources_survive_without_mutating_or_read_receipts(self):
        before_exposure = exposure(self.store, self.iid)
        data = report_data(self.store, self.iid, True, True)
        data['investigation'].update(run_status='partial', summary='Exact <words> & *qualifications*.',
                                     stop_reason='The review did not finish.')
        metric = data['main_accounting']['session']['prompt_tokens']
        metric.update(value=None, known_subtotal=123, known=1, eligible=3)
        before = copy.deepcopy(data)
        output = render_markdown(data)
        self.assertIn(text(data['investigation']['summary']), output)
        self.assertIn('Investigation: partial', output)
        self.assertIn('The review did not finish', output)
        self.assertIn('| Input total | Unknown | 1/3 recorded; Known subtotal 123', output)
        for label in ('Uncached input', 'Cache write', 'Cache read', 'Output', 'Recorded duration', 'Observed span'):
            self.assertIn(label, output)
        self.assertIn('## Turn', output)
        self.assertNotIn('Turn ?', output)
        self.assertIn('No recommendations saved', output)
        for sid, source in data['sources'].items():
            self.assertIn('<a id="'+anchor(sid)+'"></a>', output)
            if source.get('text'): self.assertIn(source['text'], output)
        self.assertEqual(data, before)
        self.assertEqual(exposure(self.store, self.iid), before_exposure)

    def test_fences_protect_long_sources_thinking_and_exact_replacement(self):
        data = report_data(self.store, self.iid, True, True)
        sid = next(iter(data['sources']))
        source = '  exact source\n```\n</script><script>alert(1)</script>\n' + 'x'*12000
        thinking = 'Captured fixture thinking\n````\n  indentation retained'
        data['sources'][sid]['text'] = source
        data['sources'][sid]['content_metadata'] = {'thinking_text':[{'text':thinking, 'evidence_projection':False}]}
        replacement = '  replacement\n```md\nexact\n```\n'
        data['recommendations'] = [{'id':'fixture-proposal','recommendation':{
            'title':'Synthetic proposal', 'target_kind':'claude_md', 'edit':{
                'operation':'replace', 'target_path':'/fixture/CLAUDE.md', 'scope':'Fixture only',
                'location':'Check instruction', 'original_text':'before\n', 'replacement_text':replacement}}}]
        output = render_markdown(data)
        self.assertIn('````text\n'+source+'\n````', output)
        self.assertIn('`````text\n'+thinking+'\n`````', output)
        self.assertIn('````text\n'+replacement+'````', output)
        self.assertIn('Captured thinking · not execution evidence', output)
        rendered = render_report({**data, 'recommendations':[]})
        # Source text is referenced, not repeated in the precomputed plan, and
        # it cannot terminate the JSON script element.
        plan = json.loads(re.search(r'id="markdown-export">(.*?)</script>', rendered, re.S).group(1))
        self.assertNotIn(source, ''.join(p for p in plan if isinstance(p, str)))
        self.assertNotIn(thinking, ''.join(p for p in plan if isinstance(p, str)))
        resolved = ''.join(p if isinstance(p,str) else
            data['sources'][p['source_id']]['content_metadata']['thinking_text'][p['thinking_index']]['text']
            if 'thinking_index' in p else data['sources'][p['source_id']]['text'] for p in plan)
        self.assertEqual(resolved, render_markdown({**data, 'recommendations':[]}))
        self.assertNotIn('</script><script>alert(1)', rendered)

    def test_absent_source_text_and_missing_children_are_explicit(self):
        data = report_data(self.store, self.iid)
        data['scope']['capture_gaps']['missing_child_traces'] = [{'child_agent_id':'synthetic-child'}]
        output = render_markdown(data)
        self.assertIn('Source text was not included in this export', output)
        self.assertIn('synthetic-child', output)
        self.assertNotIn('FAILED (failures=1)', output)
        self.assertNotIn('```text\n\n```', output)

    def test_cli_api_export_honors_disclosure_and_refuses_overwrite(self):
        target = self.root/'saved.md'
        with self.assertRaises(AnalyzerError):
            export_session_investigation(self.store,self.iid,target,'md',True,False)
        self.assertFalse(target.exists())
        result = export_session_investigation(self.store,self.iid,target,'md',True,True)
        self.assertFalse(result['model_text_edited'])
        self.assertEqual(target.read_text(),render_markdown(report_data(self.store,self.iid,True,True)))
        with self.assertRaisesRegex(AnalyzerError,'overwrite'):
            export_session_investigation(self.store,self.iid,target,'md')
        self.assertEqual(target.stat().st_mode & 0o777,0o600)
        with self.assertRaises(AnalyzerError):
            export_session_investigation(self.store,self.iid,self.root/'wrong.md','markdown')
        cli_target=self.root/'cli.md'
        result=subprocess.run([sys.executable,'-m','ally_analyzer','--data-dir',str(self.root/'store'),
                               'export-session',self.iid,str(cli_target),'--format','md'],
                              capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(cli_target.read_text(),render_markdown(report_data(self.store,self.iid)))

    def test_missing_review_and_unfinalized_draft_stay_qualified(self):
        data = report_data(self.store, self.iid)
        data['investigation'].update(run_status='partial',review_workflow={'latest_draft_id':'draft'})
        data['conclusion_drafts']=[{'id':'draft','conclusion':{'title':'Unreviewed title','summary':'Needs correction.'}}]
        output=render_markdown(data)
        self.assertIn('No observed outcome has been saved',output)
        self.assertIn('Latest Claude draft · not finalized',output)
        self.assertNotIn('# Unreviewed title',output)


if __name__ == '__main__': unittest.main()
