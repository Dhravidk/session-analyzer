"""Bounded POSIX MCP subprocess I/O for offline package checks, never Claude."""
import json
import os
import selectors
import signal
import subprocess
import tempfile
import time


class MCPProcess:
    def __init__(self, command, *, cwd=None, env=None, timeout=20, cleanup_timeout=2):
        self.timeout, self.cleanup_timeout = timeout, cleanup_timeout
        self.buffer = b''
        self.next_id = 0
        self.stderr = tempfile.TemporaryFile()
        try:
            self.process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=self.stderr, bufsize=0, start_new_session=True)
            os.set_blocking(self.process.stdin.fileno(), False)
            os.set_blocking(self.process.stdout.fileno(), False)
        except BaseException:
            if hasattr(self, 'process'): self.close()
            else: self.stderr.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        self.close()

    def close(self):
        """Reap the child even after timeout, assertion failure or blocked stdin."""
        try:
            if self.process.poll() is None:
                try: os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                try: self.process.wait(timeout=self.cleanup_timeout)
                except subprocess.TimeoutExpired:
                    try: os.killpg(self.process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    self.process.wait(timeout=self.cleanup_timeout)
        finally:
            for stream in (self.process.stdin, self.process.stdout, self.stderr):
                stream.close()

    def send(self, message, *, timeout=None):
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        pending = memoryview((json.dumps(message)+'\n').encode('utf-8'))
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdin, selectors.EVENT_WRITE)
            while pending:
                remaining = deadline-time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise TimeoutError('MCP request write exceeded its deadline')
                try: written = os.write(self.process.stdin.fileno(), pending)
                except BlockingIOError: continue
                if written == 0: raise EOFError('MCP stdin closed before the request was written')
                pending = pending[written:]

    def receive(self, *, timeout=None, max_bytes=1024*1024):
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            while True:
                line, separator, rest = self.buffer.partition(b'\n')
                if len(line) > max_bytes:
                    raise AssertionError('MCP response exceeded the bounded line size')
                if separator:
                    self.buffer = rest
                    return json.loads(line)
                remaining = deadline-time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise TimeoutError('MCP response read exceeded its deadline')
                try: chunk = os.read(self.process.stdout.fileno(), min(65536, max_bytes+1-len(self.buffer)))
                except BlockingIOError: continue
                if not chunk: raise EOFError('MCP process ended before a complete response')
                self.buffer += chunk

    def request(self, method, params):
        self.next_id += 1
        self.send({'jsonrpc':'2.0', 'id':self.next_id, 'method':method, 'params':params})
        result = self.receive()
        if result.get('id') != self.next_id:
            raise AssertionError('MCP response ID does not match the request')
        return result

    def notify(self, method, params=None):
        self.send({'jsonrpc':'2.0', 'method':method, 'params':params or {}})
