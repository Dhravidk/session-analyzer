"""Synthetic misbehaving subprocesses exercise deadlines/cleanup, never Claude."""
import sys
import signal
import time
import unittest

from tests.mcp_process import MCPProcess


class PackagingProcessTests(unittest.TestCase):
    def assert_closed(self, client):
        self.assertIsNotNone(client.process.poll())
        self.assertTrue(client.process.stdin.closed)
        self.assertTrue(client.process.stdout.closed)
        self.assertTrue(client.stderr.closed)

    def test_unresponsive_process_times_out_and_is_killed_even_if_term_ignored(self):
        code = 'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print(\'{"ready":true}\',flush=True);time.sleep(60)'
        started=time.monotonic()
        with self.assertRaisesRegex(TimeoutError,'response read'):
            with MCPProcess([sys.executable,'-u','-c',code],timeout=.2,cleanup_timeout=.2) as client:
                self.assertEqual(client.receive(timeout=3),{'ready':True})
                client.request('ping',{})
        self.assertLess(time.monotonic()-started,5)
        self.assertEqual(client.process.returncode,-signal.SIGKILL)
        self.assert_closed(client)

    def test_assertion_failure_reaps_the_child_and_closes_pipes(self):
        code = 'import time;print(\'{"ready":true}\',flush=True);time.sleep(60)'
        with self.assertRaisesRegex(AssertionError,'Synthetic assertion failure'):
            with MCPProcess([sys.executable,'-u','-c',code],cleanup_timeout=.2) as client:
                self.assertEqual(client.receive(timeout=3),{'ready':True})
                raise AssertionError('Synthetic assertion failure')
        self.assert_closed(client)

    def test_partial_line_has_a_deadline(self):
        code = 'import os,time;print(\'{"ready":true}\',flush=True);os.write(1,b\'{"partial":\');time.sleep(60)'
        with self.assertRaisesRegex(TimeoutError,'response read'):
            with MCPProcess([sys.executable,'-u','-c',code],timeout=.3,cleanup_timeout=.2) as client:
                self.assertEqual(client.receive(timeout=3),{'ready':True})
                client.receive()
        self.assertEqual(client.buffer,b'{"partial":')
        self.assert_closed(client)

    def test_unterminated_oversized_response_is_bounded(self):
        code = 'import os,time;os.write(1,b"x"*2048);time.sleep(60)'
        with self.assertRaisesRegex(AssertionError,'bounded line size'):
            with MCPProcess([sys.executable,'-u','-c',code],cleanup_timeout=.2) as client:
                client.receive(max_bytes=256,timeout=3)
        self.assertEqual(len(client.buffer),257)
        self.assert_closed(client)

    def test_blocked_stdin_write_has_a_deadline_and_cleanup(self):
        code = 'import time;print(\'{"ready":true}\',flush=True);time.sleep(60)'
        with self.assertRaisesRegex(TimeoutError,'request write'):
            with MCPProcess([sys.executable,'-u','-c',code],timeout=.2,cleanup_timeout=.2) as client:
                self.assertEqual(client.receive(timeout=3),{'ready':True})
                client.notify('synthetic-large-request',{'payload':'x'*(1024*1024)})
        self.assert_closed(client)

    def test_early_eof_also_closes_process_handles(self):
        with self.assertRaises(EOFError):
            with MCPProcess([sys.executable,'-c','pass'],timeout=3) as client:
                client.receive()
        self.assert_closed(client)


if __name__=='__main__':unittest.main()
