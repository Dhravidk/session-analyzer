"""Saved local explanations render verbatim; fixtures do not certify model quality."""
import copy
import json
import re
import unittest
from ally_analyzer.session_investigation import save_incident
from tests import test_session_story as fixture


class StoryPresentationTests(unittest.TestCase):
    contract_version='single-session-v2'
    setUp=fixture.SessionStoryTests.setUp
    load=fixture.SessionStoryTests.load
    read=fixture.SessionStoryTests.read
    read_all=fixture.SessionStoryTests.read_all
    refs=fixture.SessionStoryTests.refs
    incident=fixture.SessionStoryTests.incident
    episode=fixture.SessionStoryTests.episode
    verification=fixture.SessionStoryTests.verification
    guided=fixture.SessionStoryTests.guided

    def test_saved_events_drive_turn_titles_without_mutating_report_data(self):
        from ally_analyzer.session_report import report_data, render_report
        from ally_analyzer.session_finding_links import finding_links
        self.read_all();saved=save_incident(self.store,self.iid,self.guided())
        data=report_data(self.store,self.iid,True,True);before=copy.deepcopy(data)
        rendered=render_report(data)
        payload=json.loads(re.search(r'id="report-data">(.*?)</script>',rendered,re.S).group(1))
        self.assertEqual(payload,before);self.assertEqual(data,before)
        incident=data['incidents'][0]
        links=finding_links(data,incident)
        for event in saved['incident']['reader_guide']['events']:
            linked=[(tid,link) for tid,link in links.items() if event in link['events']]
            self.assertEqual(len(linked),1)
            row=re.search(r'<tr id="'+linked[0][0]+r'".*?</tr>',rendered,re.S).group(0)
            self.assertIn('data-finding-event="'+event['key']+'"',row)
            self.assertIn('>'+event['title']+'</span>',row)
            self.assertNotIn('>Failure and recovery<',row)
        self.assertIn('class="finding-answer"',rendered)
        self.assertIn('The repaired fixture passed its check.',rendered)
        self.assertIn('<summary>Classifications · complete finding</summary>',rendered)
        self.assertIn('data-finding="'+incident['id']+'">Synthetic fixture repair</button>',rendered)


if __name__=='__main__':unittest.main()
