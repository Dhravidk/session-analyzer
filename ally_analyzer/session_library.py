"""Local session library. Directory discovery never calls a model.

Only explicitly selected roots are scanned. Reports are immutable snapshots;
the existing importer, investigator and renderer own their respective work.
"""
import argparse
import hashlib
import json
import math
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from . import __version__
from .engine import analyze_dataset
from .ingest import import_bundle
from .session_report import export_session_investigation, render_report
from .session_markdown import render_markdown
from .session_scope import start_session_investigation
from .session_navigation import session_key, report_revision, read_revision, compare_revision, navigation_status
from .store import Store
from .trajectory import trajectory_text
from .util import AnalyzerError, canonical, utc_now, timestamp

ROOT = Path(__file__).resolve().parent.parent
SCAN_BYTES = 1024 * 1024
MAX_FILES = 10000


def folder_label(path):
    """Do not attempt to decode Claude's ambiguous hyphenated folder names."""
    parts = str(path).replace('\\', '/').rstrip('/').split('/')
    return '/'.join(p for p in parts[-2:] if p) or '/'


def write_json(path, data):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
    temporary.chmod(0o600)
    temporary.replace(path)


def safe_path(root, relative):
    path = root / relative
    if path.is_absolute() and root not in path.parents:
        raise AnalyzerError('Path outside selected directory')
    for part in (path, *path.parents):
        if part == root: break
        if part.is_symlink(): raise AnalyzerError('Symlinked session paths are not supported')
    if root not in path.resolve().parents:
        raise AnalyzerError('Path outside selected directory')
    return path


def metadata(path, root):
    """A bounded literal preview; not a session summary or a complete inventory."""
    sid, cwd, request, recorded, valid = None, None, '', None, 0
    title, activity = None, None
    malformed = 0
    request_truncated = False
    consumed = 0
    with path.open('rb') as stream:
        while consumed < SCAN_BYTES:
            line = stream.readline(SCAN_BYTES - consumed + 1)
            if not line: break
            consumed += len(line)
            if consumed > SCAN_BYTES: break
            try:
                record = json.loads(line)
                if not isinstance(record, dict): continue
            except (ValueError, UnicodeError, RecursionError):
                malformed += 1
                continue
            valid += 1
            if record.get('isSidechain') is True: continue
            if isinstance(record.get('sessionId'), str): sid = sid or record['sessionId']
            if isinstance(record.get('cwd'), str): cwd = cwd or record['cwd']
            if isinstance(record.get('timestamp'), str): recorded = recorded or record['timestamp']
            at = timestamp(record.get('timestamp'))
            if at is not None: activity = max(activity or at, at)
            if record.get('type') == 'custom-title' and isinstance(record.get('customTitle'), str):
                title = record['customTitle'].strip() or title
            message = record.get('message', {})
            if not isinstance(message, dict): message = {}
            content = message.get('content', record.get('content'))
            if (record.get('type') == 'user' or message.get('role') == 'user') and not request:
                if isinstance(content, list) and any(isinstance(b, dict) and b.get('type') == 'tool_result' for b in content): continue
                if record.get('isMeta') or record.get('isCompactSummary'): continue
                request, _ = trajectory_text({'message': {'content': content}})
                request_truncated = len(request) > 600
                request = request[:600]
    stat = path.stat()
    # Native activity/title records can be near the end of a long session. This
    # bounded tail is discovery only; freshness uses the full scoped revision.
    if stat.st_size > SCAN_BYTES:
        with path.open('rb') as stream:
            stream.seek(max(SCAN_BYTES, stat.st_size - SCAN_BYTES))
            stream.readline()
            for line in stream:
                try: record = json.loads(line)
                except (ValueError, UnicodeError, RecursionError): continue
                if not isinstance(record, dict) or record.get('isSidechain'): continue
                at = timestamp(record.get('timestamp'))
                if at is not None: activity = max(activity or at, at)
                if record.get('type') == 'custom-title' and isinstance(record.get('customTitle'), str):
                    title = record['customTitle'].strip() or title
    relative = path.relative_to(root).as_posix()
    return {'id': hashlib.sha256(relative.encode()).hexdigest()[:24], 'relative_path': relative,
            'session_id': sid or path.stem, 'explicit_session_id': bool(sid), 'folder_path': cwd or str(path.parent),
            'folder_label': folder_label(cwd or path.parent), 'preview': request,
            'title': title, 'activity_at': activity, 'activity_basis': 'recorded timestamps in bounded discovery' if activity else 'file modification time; activity time unavailable',
            'request_preview_truncated': request_truncated,
            'recorded_at': recorded, 'modified_at': stat.st_mtime, 'bytes': stat.st_size,
            'scan_limit_bytes': SCAN_BYTES, 'preview_partial': stat.st_size > consumed,
            'malformed_preview_lines': malformed, 'readable_records_in_preview': valid,
            'stat_key': [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino]}


class SessionLibrary:
    def __init__(self, directory, state_dir, claude=None, reports=()):
        supplied = Path(directory).expanduser()
        if supplied.is_symlink(): raise AnalyzerError('Choose a directory, not a symlink')
        self.root = supplied.resolve(strict=True)
        if not self.root.is_dir(): raise AnalyzerError('Choose a session directory')
        self.home = Path(state_dir).expanduser().resolve()
        if self.home == self.root or self.root in self.home.parents or self.home in self.root.parents:
            raise AnalyzerError('Library storage and session directory must not contain one another')
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.claude = shutil.which(claude or 'claude')
        self.lock = threading.RLock()
        self.worker = None
        self.process = None
        self.catalog = {}
        self.file_metadata = {}
        self.revision_cache = {}
        self.embedded_cache = {}
        self.scan_limits = []
        self.state_file = self.home / 'library.json'
        self.state = json.loads(self.state_file.read_text()) if self.state_file.exists() else {'root': str(self.root), 'reports': [], 'jobs': []}
        if self.state['root'] != str(self.root): raise AnalyzerError('This library store belongs to a different directory')
        for job in self.state['jobs']:
            if job['status'] in ('queued', 'running'):
                job.update(status='interrupted', error='Library stopped before this job was recorded as finished.')
        self.refresh()
        self.admit_reports(reports)
        self.save()

    def save(self):
        write_json(self.state_file, self.state)

    def refresh(self):
        with self.lock:
            previous, catalog, warnings, files = self.file_metadata, {}, [], {}
            examined = 0
            for base, dirs, names in os.walk(self.root, followlinks=False):
                depth = len(Path(base).relative_to(self.root).parts)
                dirs[:] = sorted(d for d in dirs if d != 'subagents' and not d.startswith('.') and not (Path(base)/d).is_symlink())
                if depth >= 3:
                    if dirs: warnings.append('Directories deeper than three levels were not scanned.')
                    dirs[:] = []
                for name in sorted(names):
                    if not name.endswith(('.jsonl', '.log')): continue
                    examined += 1
                    if examined > MAX_FILES: break
                    path = Path(base)/name
                    if path.is_symlink() or not path.is_file(): continue
                    relative = path.relative_to(self.root).as_posix()
                    key = hashlib.sha256(relative.encode()).hexdigest()[:24]
                    try:
                        stat = path.stat()
                        cached = previous.get(key)
                        item = cached if cached and cached['stat_key'] == [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino] else metadata(path, self.root)
                        files[key] = item
                        identity = session_key(item)
                        entry = {**item, 'id': identity, 'path_keys': [key], 'source_paths': [relative]}
                        if identity in catalog:
                            old = catalog[identity]
                            if (old.get('activity_at') or old['modified_at'], old['bytes']) > (entry.get('activity_at') or entry['modified_at'], entry['bytes']):
                                old, entry = entry, old
                            entry['path_keys'] = sorted(set(entry['path_keys'] + old['path_keys']))
                            entry['source_paths'] = sorted(set(entry['source_paths'] + old['source_paths']))
                        catalog[identity] = entry
                    except (OSError, ValueError) as exc:
                        warnings.append('Could not read '+relative+': '+str(exc))
                if examined > MAX_FILES:
                    warnings.append('Discovery stopped at 10,000 log files. Select a narrower directory.')
                    break
            self.file_metadata, self.catalog, self.scan_limits = files, catalog, sorted(set(warnings))
            return self.snapshot()

    def fingerprint(self, item):
        # Cache invalidator only. Freshness below compares importer payload hashes.
        path = safe_path(self.root, item['relative_path'])
        stat = path.stat()
        stamps = [(item['relative_path'], stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)]
        sid = item['session_id']
        if sid and all(c.isalnum() or c in '-_' for c in sid):
            children = path.parent/sid/'subagents'
            if children.exists():
                safe_path(self.root, children.relative_to(self.root))
                for base, dirs, files in os.walk(children, followlinks=False):
                    for name in dirs+files:
                        if (Path(base)/name).is_symlink(): raise AnalyzerError('Subagent directory contains a symlink')
                    for name in files:
                        p = Path(base)/name
                        if not name.endswith(('.jsonl', '.log', '.meta.json')): continue
                        s = p.stat()
                        stamps.append((p.relative_to(self.root).as_posix(), s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_ino))
                        if len(stamps) > MAX_FILES: raise AnalyzerError('Too many companion files')
        return hashlib.sha256(canonical(sorted(stamps)).encode()).hexdigest()

    def snapshot(self):
        with self.lock:
            items = []
            for item in self.catalog.values():
                latest = self.latest_report(item)
                freshness = self.freshness(item, latest)
                jobs = [j for j in self.state['jobs'] if j['session_key'] in [item['id'], *item['path_keys']] and j['action'] == 'investigate']
                job = jobs[-1] if jobs else None
                if job and latest and job.get('finished_at', '') < latest.get('analysis_at', latest['created_at']) and job['status'] not in ('queued', 'running'):
                    job = None
                visible = self.public_report(latest) if latest else None
                items.append({**item, 'latest_report': visible, 'freshness': freshness,
                              'job': job, 'states': navigation_status(latest, freshness, job)})
            items.sort(key=lambda x: (-(x.get('activity_at') or x['modified_at']), x['id']))
            reports = [x['latest_report'] for x in items if x['latest_report']]
            return {'version': __version__, 'root': str(self.root), 'folder_label': folder_label(self.root),
                    'claude_available': bool(self.claude), 'sessions': items, 'reports': reports,
                    'jobs': self.state['jobs'], 'limits': self.scan_limits}

    @staticmethod
    def public_report(record):
        return {k:v for k,v in record.items() if k not in ('html_path', 'json_path', 'revision', 'fingerprint', 'import_key')}

    def matches_report(self, record, item):
        if record.get('session_key'):
            return record['session_key'] in [item['id'], *item['path_keys']]
        # Ambiguous imported IDs are not associated by title, short folder label,
        # or a guess at the original path.
        candidates = [x for x in self.catalog.values() if x['session_id'] == record['session_id']]
        return len(candidates) == 1 and candidates[0]['id'] == item['id']

    def latest_report(self, item):
        rows = [r for r in self.state['reports'] if self.matches_report(r, item)]
        analyses = [r for r in rows if r['kind'] != 'preview']
        return max(analyses or rows, key=lambda r: (timestamp(r.get('analysis_at') or r['created_at']) or 0,
                                                  timestamp(r['saved_at']) or 0), default=None)

    def freshness(self, item, record):
        if not record: return {'state': 'not_analyzed', 'reason': 'No saved analysis.'}
        try:
            if 'revision' not in record:
                data = json.loads(Path(record['json_path']).read_text())
                record['revision'] = report_revision(data)
                record['analysis_at'] = data['investigation'].get('finished_at') or record['created_at']
            stamp = self.fingerprint(item)
            cached = self.revision_cache.get(item['id'])
            if not cached or cached[0] != stamp:
                current = read_revision(safe_path(self.root, item['relative_path']), item['session_id'])
                if self.fingerprint(item) != stamp:
                    return {'state': 'unknown', 'reason': 'The source changed during comparison. Refresh to compare again.'}
                self.revision_cache[item['id']] = (stamp, current)
            return compare_revision(record['revision'], self.revision_cache[item['id']][1])
        except (AnalyzerError, OSError, ValueError) as exc:
            return {'state': 'unknown', 'reason': str(exc)}

    def admit_reports(self, folders):
        """Explicit saved runner exports only. Re-render data, never execute imported HTML."""
        admitted = {r.get('import_key') for r in self.state['reports']}
        session_ids = {i['session_id'] for i in self.catalog.values()}
        for folder in folders:
            source = Path(folder).expanduser().resolve(strict=True)
            candidates = [source] if source.is_file() else source.glob('**/claude-investigation.json')
            for count, path in enumerate(candidates):
                if count >= MAX_FILES: raise AnalyzerError('Too many saved reports')
                if path.is_symlink() or any(p.is_symlink() for p in path.parents): continue
                if path.stat().st_size > 512*1024*1024: continue
                raw = path.read_bytes()
                key = hashlib.sha256(raw).hexdigest()
                if key in admitted: continue
                try: data = json.loads(raw)
                except (ValueError, UnicodeError):
                    self.scan_limits.append('A selected saved report could not be parsed: '+str(path))
                    continue
                if not isinstance(data, dict): continue
                if data.get('report_version') != 'session-investigation-v2': continue
                if not isinstance(data.get('investigation'),dict) or data['investigation'].get('root_session_id') not in session_ids: continue
                try: rendered=render_report(data)
                except (KeyError, TypeError, ValueError):
                    self.scan_limits.append('A selected report has an unsupported data shape: '+str(path))
                    continue
                dest = self.home/'reports'/uuid.uuid4().hex
                dest.mkdir(parents=True, mode=0o700)
                (dest/'report.json').write_bytes(raw)
                (dest/'report.html').write_text(rendered)
                self.register_report(dest/'report.json', dest/'report.html', None, None, 'imported', key)
                admitted.add(key)

    def register_report(self, json_path, html_path, session_key, fingerprint, kind, import_key=None):
        data = json.loads(json_path.read_text())
        run = data['investigation']
        if data.get('report_version') != 'session-investigation-v2' or run.get('run_status') not in ('created','running','completed','partial','failed'):
            raise AnalyzerError('Workflow returned an unsupported report')
        if session_key and (not self.catalog.get(session_key) or self.catalog[session_key]['session_id'] != run['root_session_id']):
            raise AnalyzerError('Workflow report belongs to a different session')
        # Exercise the standard renderer before admitting a report. A corrupt
        # update must never displace a usable saved analysis.
        render_report(data)
        item = {'id': uuid.uuid4().hex, 'session_key': session_key, 'session_id': run['root_session_id'],
                'created_at': run['created_at'], 'saved_at': utc_now(), 'kind': kind,
                'analysis_at': run.get('finished_at') or run['created_at'], 'revision': report_revision(data),
                'renderer_version': __version__,
                'status': 'not_run' if kind == 'preview' else run['run_status'],
                'title': run.get('title'), 'conclusion': run.get('conclusion'),
                'fingerprint': fingerprint, 'import_key': import_key,
                'html_path': str(html_path), 'json_path': str(json_path)}
        with self.lock:
            self.state['reports'].append(item)
            self.save()
        return item

    def start(self, payload):
        with self.lock:
            if self.worker and self.worker.is_alive(): raise AnalyzerError('A library job is already running')
            if not isinstance(payload.get('session'),str): raise AnalyzerError('Select a discovered session ID')
            item = self.catalog.get(payload.get('session'))
            if not item: raise AnalyzerError('Select a discovered session')
            action = payload.get('action')
            if action not in ('preview', 'investigate'): raise AnalyzerError('Unknown action')
            budget, timeout = payload.get('budget', 3), payload.get('timeout', 600)
            if action == 'investigate':
                if payload.get('allow_content') is not True: raise AnalyzerError('Approve controlled excerpts before running Claude')
                if not self.claude: raise AnalyzerError('Claude executable unavailable; relaunch with --claude /path/to/claude')
                if isinstance(budget, bool) or not isinstance(budget, (int,float)) or not math.isfinite(budget) or not 0 < budget <= 100:
                    raise AnalyzerError('Budget must be greater than zero and at most $100')
                if type(timeout) is not int or not 30 <= timeout <= 3600: raise AnalyzerError('Timeout must be 30–3600 seconds')
            fingerprint = self.fingerprint(item)
            if action == 'preview':
                match = next((r for r in reversed(self.state['reports']) if r['session_key'] == item['id'] and r['kind'] == 'preview' and r['fingerprint'] == fingerprint and r.get('renderer_version') == __version__), None)
                if match: return {'report_id': match['id']}
            job = {'id': uuid.uuid4().hex, 'session_key': item['id'], 'action': action, 'status': 'queued',
                   'started_at': utc_now(), 'report_id': None, 'error': None}
            self.state['jobs'].append(job)
            self.save()
            self.worker = threading.Thread(target=self.execute, args=(job, dict(item), fingerprint, budget, timeout), daemon=True)
            self.worker.start()
            return {'job_id': job['id']}

    def execute(self, job, item, fingerprint, budget, timeout):
        try:
            with self.lock:
                job['status'] = 'running'; self.save()
            path = safe_path(self.root, item['relative_path'])
            base = self.home/'runs'/job['id']
            base.mkdir(parents=True, mode=0o700)
            if job['action'] == 'preview':
                store = Store(base/'store')
                imported = import_bundle(store, path, namespace='session-library')
                aid = analyze_dataset(store, imported['dataset_id'])['analysis_id']
                run = start_session_investigation(store, aid, item['session_id'], 'Local log inspection; no Claude investigation requested.')['investigation']
                html_path, json_path = base/'report.html', base/'report.json'
                for target, format in ((html_path, 'html'), (json_path, 'json')):
                    export_session_investigation(store, run['id'], target, format, include_source_text=True, allow_content=True)
            else:
                result = base/'investigation'
                command = [sys.executable, str(ROOT/'scripts/ally-session.py'), 'investigate', '--source', str(path),
                           '--session-id', item['session_id'], '--work-dir', str(result), '--claude', self.claude,
                           '--plugin', str(ROOT), '--allow-content', '--include-source-text-in-report',
                           '--max-budget-usd', str(budget), '--timeout', str(timeout)]
                write_json(base/'launch.json', {'argv': command, 'closed_stdin': True, 'source_change_detector': fingerprint})
                with (base/'stdout.log').open('wb') as out, (base/'stderr.log').open('wb') as err:
                    self.process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)
                    job['exit_code'] = self.process.wait()
                    self.process = None
                html_path, json_path = result/'claude-investigation.html', result/'claude-investigation.json'
                if not html_path.exists() or not json_path.exists():
                    raise AnalyzerError('Claude workflow ended without a report. Details are retained in '+str(base))
            record = self.register_report(json_path, html_path, item['id'], fingerprint, job['action'])
            with self.lock:
                job.update(status='saved', report_id=record['id'], source_changed_during_run=self.fingerprint(item) != fingerprint)
        except Exception as exc:
            with self.lock: job.update(status='failed', error=str(exc))
        finally:
            with self.lock:
                job['finished_at'] = utc_now()
                self.save()

    def report(self, report_id):
        with self.lock:
            record = next((r for r in self.state['reports'] if r['id'] == report_id), None)
            if not record: raise AnalyzerError('Unknown report')
            item = next((i for i in self.catalog.values() if self.matches_report(record, i)), None)
            freshness = self.freshness(item, record) if item else {'state':'unknown', 'reason':'The source is not in this directory.'}
            return {**self.public_report(record), 'freshness': freshness,
                    'source_changed': True if freshness['state'] in ('new_activity','changed') else False if freshness['state'] == 'current' else None}

    def embedded_report(self, record):
        if record['id'] not in self.embedded_cache:
            data = json.loads(Path(record['json_path']).read_text())
            self.embedded_cache[record['id']] = render_report(data, embedded=True).encode()
        return self.embedded_cache[record['id']]


def make_server(library, port=0):
    token = secrets.token_urlsafe(24)
    prefix = '/library/'+token+'/'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass

        def respond(self, status, body, content_type='application/json', download=None):
            if not isinstance(body, bytes): body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if download: self.send_header('Content-Disposition','attachment; filename="'+download+'"')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'none'") if content_type != 'text/html; charset=utf-8' else None
            self.end_headers()
            self.wfile.write(body)

        def route(self):
            expected_host = '127.0.0.1:'+str(self.server.server_port)
            if self.headers.get('Host') != expected_host: raise AnalyzerError('Host not allowed')
            path = urlsplit(self.path).path
            if not path.startswith(prefix): raise AnalyzerError('Unknown library URL')
            return path[len(prefix):]

        def do_GET(self):
            try:
                route = self.route()
                if route == 'api/catalog': return self.respond(200, library.snapshot())
                if route.startswith('api/report/'):
                    return self.respond(200, library.report(route.removeprefix('api/report/')))
                if route.startswith(('reports/','downloads/')):
                    name = route.split('/',1)[1]
                    rid, ext = name.rsplit('.', 1)
                    with library.lock: record = next((r for r in library.state['reports'] if r['id'] == rid), None)
                    if record and ext in ('html', 'json', 'md'):
                        if ext=='html':
                            # Export the current presentation of the same immutable
                            # data; never replace the historically saved HTML file.
                            body=(library.embedded_report(record) if route.startswith('reports/') else
                                  render_report(json.loads(Path(record['json_path']).read_text())).encode())
                        elif ext=='md':body=render_markdown(json.loads(Path(record['json_path']).read_text())).encode()
                        else:body=Path(record['json_path']).read_bytes()
                        mime={'html':'text/html; charset=utf-8','md':'text/markdown; charset=utf-8','json':'application/json'}[ext]
                        return self.respond(200, body, mime,
                                            'ally-'+rid+'.'+ext if route.startswith('downloads/') else None)
                assets = {'': ('session_library.html', 'text/html; charset=utf-8'),
                          'app.js': ('session_library.js', 'text/javascript'), 'style.css': ('session_library.css', 'text/css')}
                if route.startswith('icons/') and route.removeprefix('icons/') in {p.name for p in Path(__file__).with_name('icons').glob('*.svg')}:
                    return self.respond(200, Path(__file__).with_name('icons').joinpath(route.removeprefix('icons/')).read_bytes(), 'image/svg+xml')
                if route in assets:
                    name, mime = assets[route]
                    return self.respond(200, Path(__file__).with_name(name).read_bytes(), mime)
                self.respond(404, {'error': 'Not found'})
            except (AnalyzerError, OSError, ValueError) as exc: self.respond(404, {'error': str(exc)})

        def do_POST(self):
            try:
                route = self.route()
                origin = 'http://127.0.0.1:'+str(self.server.server_port)
                if self.headers.get('Origin') != origin or self.headers.get('X-Ally-Library') != token:
                    raise AnalyzerError('Request must come from this library')
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 8192: raise AnalyzerError('Invalid request size')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict): raise AnalyzerError('Expected an object')
                if route == 'api/refresh': return self.respond(200, library.refresh())
                if route == 'api/start': return self.respond(200, library.start(payload))
                self.respond(404, {'error': 'Not found'})
            except (AnalyzerError, ValueError, OSError) as exc: self.respond(400, {'error': str(exc)})
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server, 'http://127.0.0.1:'+str(server.server_port)+prefix


def main(argv=None):
    p = argparse.ArgumentParser(description='Browse an explicitly selected local Claude session directory. Browsing does not call Claude.')
    p.add_argument('directory', nargs='?', default='.', help='Session/project directory, or ~/.claude/projects (default: current directory)')
    p.add_argument('--data-dir', help='Private library storage; default: ~/.ally-session-analyzer/libraries/<directory hash>')
    p.add_argument('--claude', help='Approved Claude executable; defaults to PATH lookup')
    p.add_argument('--reports', action='append', default=[], help='Explicit saved runner report directory or JSON export; may repeat')
    p.add_argument('--port', type=int, default=0)
    p.add_argument('--no-open', action='store_true')
    p.add_argument('--detach', action='store_true', help='Keep the local browser running in the background')
    p.add_argument('--ready-file', help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    os.umask(0o077)
    root = Path(args.directory).expanduser().resolve()
    home = Path(args.data_dir).expanduser().resolve() if args.data_dir else Path(os.environ.get('ALLY_ANALYZER_HOME', '~/.ally-session-analyzer')).expanduser()/'libraries'/hashlib.sha256(str(root).encode()).hexdigest()[:20]
    try:
        if args.detach:
            home.mkdir(parents=True, exist_ok=True, mode=0o700)
            ready = home/('launch-'+uuid.uuid4().hex+'.json')
            command = [sys.executable, str(ROOT/'scripts/ally-session.py'), 'browse', str(root), '--data-dir', str(home), '--port', str(args.port), '--ready-file', str(ready)]
            if args.claude: command += ['--claude', args.claude]
            if args.no_open: command += ['--no-open']
            for folder in args.reports: command += ['--reports', folder]
            with (home/'server.log').open('ab') as out:
                child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=out, stderr=out, start_new_session=True)
            for _ in range(300):
                if ready.exists():
                    print(ready.read_text()); return 0
                if child.poll() is not None: raise AnalyzerError('Library did not start; see '+str(home/'server.log'))
                time.sleep(.1)
            raise AnalyzerError('Library startup is still pending; see '+str(home/'server.log'))
        # Prevent two servers from concurrently writing the same history.
        home.mkdir(parents=True, exist_ok=True, mode=0o700)
        import fcntl
        with (home/'server.lock').open('a') as lockfile:
            try: fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                info=json.loads((home/'server.json').read_text())
                info['reused_existing_server']=True
                if args.ready_file: write_json(Path(args.ready_file), info)
                print(json.dumps(info),flush=True)
                if not args.no_open:
                    import webbrowser
                    webbrowser.open(info['url'])
                return 0
            library = SessionLibrary(args.directory, home, args.claude, args.reports)
            server, url = make_server(library, args.port)
            info = {'url': url, 'pid': os.getpid(), 'directory': str(root), 'state_dir': str(home)}
            write_json(home/'server.json', info)
            if args.ready_file: write_json(Path(args.ready_file), info)
            print(json.dumps(info), flush=True)
            if not args.no_open:
                import webbrowser
                webbrowser.open(url)
            try: server.serve_forever()
            finally: server.server_close()
        return 0
    except (AnalyzerError, OSError) as exc:
        print(str(exc), file=sys.stderr); return 2
    except KeyboardInterrupt: return 130
