"""Snapshot untrusted archives without extracting or executing their contents."""
import hashlib
import os
import re
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from .util import AnalyzerError, canonical, digest, normalized_timestamp, strict_json, utc_now

LIMITS = {"max_files": 10000, "max_expanded_bytes": 2 * 1024**3,
          "max_file_bytes": 1024**3, "max_line_bytes": 8 * 1024**2,
          "max_compressed_bytes": 1024**3}
LOG_SUFFIXES = (".jsonl", ".log")


def safe_member(name):
    p = PurePosixPath(name)
    if (not name or "\\" in name or p.is_absolute() or ".." in p.parts
            or re.match(r"^[A-Za-z]:", name) or "\x00" in name):
        raise AnalyzerError("Unsafe archive member path")
    return str(p)


def identity_from_path(path):
    parts = PurePosixPath(path).parts
    if "subagents" in parts:
        i = parts.index("subagents")
        return (parts[i - 1] if i else "unknown",
                PurePosixPath(path).stem.removeprefix("agent-"))
    return PurePosixPath(path).stem, "main"


def companion_entries(path):
    """Collect only the selected session's adjacent native subagent directory.

    Never search a home/project tree or follow a path supplied by transcript text.
    A renamed export can use its sole explicit sessionId to find the sibling.
    """
    session_ids = set()
    with path.open('rb') as stream:
        while True:
            line = stream.readline(LIMITS['max_line_bytes']+1)
            if not line: break
            if len(line)>LIMITS['max_line_bytes']:
                while line and not line.endswith(b'\n'): line=stream.readline(LIMITS['max_line_bytes']+1)
                continue
            try:
                value = strict_json(line)
                sid = value.get('sessionId') if isinstance(value,dict) else None
                if isinstance(sid,str) and sid: session_ids.add(sid)
            except (ValueError,UnicodeError,RecursionError):
                pass
            if len(session_ids)>1:
                return [], {'status':'ambiguous_root','note':'Multiple session identities in one file; select a bundle containing the intended child traces.'}
    name = next(iter(session_ids),path.stem)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',name):
        return [], {'status':'unsupported_session_identity','note':'No companion path was followed for this session identity.'}
    parent = path.parent/name
    folder = parent/'subagents'
    if parent.is_symlink() or folder.is_symlink():
        raise AnalyzerError('Session companion directories must not be symlinks')
    if not folder.is_dir():
        return [], {'status':'not_found','session_id':name,'note':'No adjacent session subagent directory was available. Delegation gaps remain visible.'}
    entries = []
    for base, dirs, files in os.walk(folder,followlinks=False):
        for item in dirs+files:
            if (Path(base)/item).is_symlink(): raise AnalyzerError('Subagent directory contains a symlink')
        for item in files:
            child = Path(base)/item
            if not child.is_file(): raise AnalyzerError('Subagent directory contains a special file')
            if not (item.endswith(LOG_SUFFIXES) or item.endswith('.meta.json')): continue
            entries.append((child.relative_to(path.parent).as_posix(),child.stat().st_size,lambda child=child:child.open('rb')))
            if len(entries)>=LIMITS['max_files']: raise AnalyzerError('Too many companion files')
    return entries, {'status':'collected','session_id':name,'companion_files':len(entries),
                     'note':'Adjacent captured logs and metadata only; collection does not establish complete child execution.'}


def import_bundle(store, source, namespace="local", labels=None, progress=None, include_subagents=True):
    if not isinstance(include_subagents,bool):
        raise AnalyzerError('include_subagents must be a boolean')
    if not isinstance(namespace, str) or not 1 <= len(namespace) <= 128:
        raise AnalyzerError("Namespace must be 1–128 characters")
    labels = labels or {}
    if (not isinstance(labels, dict) or len(labels) > 20 or
            any(not isinstance(k, str) or not isinstance(v, str) or len(v) > 200 for k, v in labels.items())):
        raise AnalyzerError("Labels must be a small string-to-string mapping")
    path = Path(source).expanduser()
    if path.is_symlink():
        raise AnalyzerError("Select a regular file or directory, not a symlink")
    path = path.resolve()
    if not path.exists():
        raise AnalyzerError("Input path does not exist")
    if path == store.root or store.root in path.parents or (path.is_dir() and path in store.root.parents):
        raise AnalyzerError("Input and analyzer storage directories must not contain one another")
    entries, archive = [], None
    collection = {'status':'selected_bundle','note':'Only the selected directory or archive is collected.'}
    try:
        if path.is_file() and zipfile.is_zipfile(path):
            if path.stat().st_size > LIMITS["max_compressed_bytes"]:
                raise AnalyzerError("Compressed archive exceeds import limit")
            archive = zipfile.ZipFile(path)
            names = set()
            for entry in archive.infolist():
                member = safe_member(entry.filename)
                mode = entry.external_attr >> 16
                if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                    raise AnalyzerError("Archive links or special files are not supported")
                if entry.is_dir():
                    continue
                if member in names:
                    raise AnalyzerError("Archive contains duplicate member paths")
                names.add(member)
                entries.append((member, entry.file_size, lambda e=entry: archive.open(e)))
        elif path.is_dir():
            for base, dirs, names in os.walk(path, followlinks=False):
                for name in dirs + names:
                    if (Path(base) / name).is_symlink():
                        raise AnalyzerError("Input directory contains a symlink")
                for name in names:
                    p = Path(base) / name
                    if not p.is_file():
                        raise AnalyzerError("Input contains a special file")
                    entries.append((p.relative_to(path).as_posix(), p.stat().st_size, lambda p=p: p.open("rb")))
                    if len(entries) > LIMITS["max_files"]:
                        raise AnalyzerError("Too many files")
        elif path.is_file() and path.suffix in LOG_SUFFIXES:
            entries.append((path.name, path.stat().st_size, lambda: path.open("rb")))
            if path.stat().st_size>LIMITS['max_file_bytes']:
                raise AnalyzerError('File exceeds import limit')
            if include_subagents:
                children,collection = companion_entries(path)
                entries.extend(children)
            else:
                collection = {'status':'parent_only','note':'Companion subagent collection was disabled by the operator.'}
        else:
            raise AnalyzerError("Expected ZIP archive, directory, or JSONL (.jsonl / .log) file")
        if not entries or not any(n.endswith(LOG_SUFFIXES) for n, _, _ in entries):
            raise AnalyzerError("Input contains no JSONL files")
        if len(entries) > LIMITS["max_files"] or sum(s for _, s, _ in entries) > LIMITS["max_expanded_bytes"]:
            raise AnalyzerError("Import exceeds file-count or expanded-size limit")
        inventory, changed = [], []
        total = 0
        for i, (name, expected_size, opener) in enumerate(sorted(entries)):
            if expected_size > LIMITS["max_file_bytes"]:
                raise AnalyzerError("File exceeds import limit")
            h, size = hashlib.sha256(), 0
            fd, tmp = tempfile.mkstemp(prefix="import-", dir=str(store.objects))
            try:
                with os.fdopen(fd, "wb") as dst, opener() as src:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        total += len(chunk)
                        if size > LIMITS["max_file_bytes"] or total > LIMITS["max_expanded_bytes"]:
                            raise AnalyzerError("Expanded content exceeds import limit")
                        h.update(chunk)
                        dst.write(chunk)
                sha = h.hexdigest()
                dest = store.objects / sha
                if dest.exists():
                    os.unlink(tmp)
                else:
                    os.replace(tmp, dest)
                    dest.chmod(0o600)
                inventory.append({"path": name, "sha256": sha, "size": size})
                if size != expected_size:
                    changed.append(name)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            if progress:
                progress({"stage": "snapshot", "files_done": i + 1, "files_total": len(entries)})
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise AnalyzerError("Could not snapshot input: " + str(exc)) from exc
    finally:
        if archive:
            archive.close()
    manifest = {"namespace": namespace, "labels": labels, "files": inventory,
                "capture_warnings": sorted(changed), "importer_version": "3", "collection":collection}
    dataset_id = "ds_" + digest(manifest)[:24]
    with store.connect() as db:
        existing = db.execute("SELECT id FROM datasets WHERE id=?", (dataset_id,)).fetchone()
        if existing:
            return {"dataset_id": dataset_id, "reused": True, "files": len(inventory)}
        db.execute("INSERT INTO datasets VALUES (?,?,?)", (dataset_id, canonical(manifest), utc_now()))
        def diagnostic(code, name, line, detail):
            d = {"code": code, "path": name, "line": line, "detail": detail}
            db.execute("INSERT OR IGNORE INTO diagnostics VALUES (?,?,?,?,?,?)",
                       (dataset_id, digest(d), code, name, line, detail))
        count = 0
        for entry in inventory:
            name, sha = entry["path"], entry["sha256"]
            db.execute("INSERT INTO files VALUES (?,?,?,?)", (dataset_id, name, sha, entry["size"]))
            if not name.endswith(LOG_SUFFIXES):
                continue
            fallback_session, fallback_agent = identity_from_path(name)
            # Exported files can be renamed to session.log. Metadata lacking a
            # sessionId belongs to the sole explicit session, when unambiguous.
            explicit_sessions = set()
            with (store.objects / sha).open("rb") as source_file:
                while True:
                    candidate = source_file.readline(LIMITS["max_line_bytes"] + 1)
                    if not candidate:
                        break
                    if len(candidate) > LIMITS["max_line_bytes"]:
                        while candidate and not candidate.endswith(b"\n"):
                            candidate = source_file.readline(LIMITS["max_line_bytes"] + 1)
                        continue
                    try:
                        obj = strict_json(candidate)
                        if isinstance(obj, dict) and isinstance(obj.get("sessionId"), str) and obj["sessionId"]:
                            explicit_sessions.add(obj["sessionId"])
                    except (ValueError, UnicodeError, RecursionError):
                        continue
                    if len(explicit_sessions) > 1:
                        break
            if len(explicit_sessions) == 1:
                fallback_session = next(iter(explicit_sessions))
            with (store.objects / sha).open("rb") as stream:
                line = 0
                while True:
                    raw = stream.readline(LIMITS["max_line_bytes"] + 1)
                    if not raw:
                        break
                    line += 1
                    if len(raw) > LIMITS["max_line_bytes"]:
                        while raw and not raw.endswith(b"\n"):
                            raw = stream.readline(LIMITS["max_line_bytes"] + 1)
                        diagnostic("oversized_record", name, line, "Record exceeded byte limit and was not parsed")
                        continue
                    if not raw.strip():
                        continue
                    try:
                        record = strict_json(raw)
                        if not isinstance(record, dict) or not isinstance(record.get("type"), str):
                            raise ValueError("Expected event object with string type")
                        payload = canonical(record)
                    except (ValueError, UnicodeError, RecursionError):
                        diagnostic("malformed_record", name, line, "Invalid UTF-8, JSON, or event shape")
                        continue
                    session = record.get("sessionId") or fallback_session
                    agent = record.get("agentId") or fallback_agent
                    if not isinstance(session, str) or not isinstance(agent, str):
                        diagnostic("malformed_identity", name, line, "Non-string session or agent identity")
                        continue
                    logical = str(record.get("uuid") or (sha + ":" + str(line)))
                    ph = digest(record)
                    eid = "ev_" + digest([namespace, logical, ph])[:24]
                    db.execute("INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (dataset_id, eid, logical, ph, session, agent, record["type"],
                                normalized_timestamp(record.get("timestamp")),
                                record.get("version") if isinstance(record.get("version"), str) else None, payload))
                    db.execute("INSERT OR IGNORE INTO provenance VALUES (?,?,?,?)", (dataset_id, eid, name, line))
                    count += 1
            if progress:
                progress({"stage": "parse", "records_done": count})
        for name in changed:
            diagnostic("input_changed_during_capture", name, None, "Size changed while capturing source")
        for row in db.execute("SELECT logical_key FROM events WHERE dataset_id=? GROUP BY logical_key HAVING COUNT(*)>1", (dataset_id,)):
            diagnostic("conflicting_event_identity", "", None, "Conflicting identity fingerprint " + digest(row[0]))
    return {"dataset_id": dataset_id, "reused": False, "files": len(inventory), "parsed_records": count}
