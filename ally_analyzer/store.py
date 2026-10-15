import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .util import AnalyzerError, canonical, strict_json

SCHEMA_VERSION = 2
SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
 id TEXT PRIMARY KEY, manifest TEXT NOT NULL, imported_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS files (
 dataset_id TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
 PRIMARY KEY(dataset_id,path));
CREATE TABLE IF NOT EXISTS events (
 dataset_id TEXT NOT NULL, id TEXT NOT NULL, logical_key TEXT NOT NULL, payload_hash TEXT NOT NULL,
 session_id TEXT NOT NULL, agent_id TEXT NOT NULL, kind TEXT NOT NULL,
 timestamp TEXT, version TEXT, raw TEXT NOT NULL,
 PRIMARY KEY(dataset_id,id));
CREATE INDEX IF NOT EXISTS events_session ON events(dataset_id,session_id,agent_id,timestamp,id);
CREATE INDEX IF NOT EXISTS events_identity ON events(dataset_id,logical_key);
CREATE TABLE IF NOT EXISTS provenance (
 dataset_id TEXT NOT NULL, event_id TEXT NOT NULL, path TEXT NOT NULL, line INTEGER NOT NULL,
 PRIMARY KEY(dataset_id,event_id,path,line));
CREATE TABLE IF NOT EXISTS diagnostics (
 dataset_id TEXT NOT NULL, id TEXT NOT NULL, code TEXT NOT NULL, path TEXT NOT NULL,
 line INTEGER, detail TEXT NOT NULL, PRIMARY KEY(dataset_id,id));
CREATE TABLE IF NOT EXISTS analyses (
 id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, configuration TEXT NOT NULL,
 summary TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS items (
 analysis_id TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL, session_ids TEXT NOT NULL,
 payload TEXT NOT NULL, PRIMARY KEY(analysis_id,kind,id));
CREATE INDEX IF NOT EXISTS items_kind ON items(analysis_id,kind,id);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, state TEXT NOT NULL, operation TEXT NOT NULL, progress TEXT NOT NULL,
 result TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS annotations (
 analysis_id TEXT NOT NULL, finding_id TEXT NOT NULL, status TEXT NOT NULL,
 note TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(analysis_id,finding_id));
CREATE TABLE IF NOT EXISTS insights (
 id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS insights_analysis ON insights(analysis_id,created_at,id);
CREATE TABLE IF NOT EXISTS insight_reviews (
 insight_id TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS insight_reviews_id ON insight_reviews(insight_id);
"""


class Store:
    def __init__(self, path=None):
        self.root = Path(path or os.environ.get("ALLY_ANALYZER_HOME") or
                         Path.home() / ".ally-session-analyzer").expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.objects = self.root / "objects"
        self.objects.mkdir(exist_ok=True, mode=0o700)
        self.db_path = self.root / "analysis.sqlite3"
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, SCHEMA_VERSION):
                raise AnalyzerError("Unsupported database schema version")
            db.execute("PRAGMA journal_mode=WAL")
            if version < SCHEMA_VERSION:
                # SQLite backup includes committed WAL pages. Keep the original
                # version readable if any DDL in the migration fails.
                if version:
                    backup = self.root / ("analysis.pre-v%d.sqlite3" % SCHEMA_VERSION)
                    if not backup.exists():
                        with sqlite3.connect(str(backup)) as target:
                            db.backup(target)
                        backup.chmod(0o600)
                from .session_schema import SCHEMA as SESSION_SCHEMA
                db.execute("BEGIN IMMEDIATE")
                for statement in (SCHEMA + SESSION_SCHEMA).split(";"):
                    if statement.strip():
                        db.execute(statement)
                db.execute("PRAGMA user_version=%d" % SCHEMA_VERSION)
        try:
            self.db_path.chmod(0o600)
        except OSError:
            pass

    @contextmanager
    def connect(self):
        db = sqlite3.connect(str(self.db_path), timeout=60)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=60000")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def analysis(self, analysis_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
        if row is None:
            raise AnalyzerError("Unknown analysis ID")
        return {"id": row["id"], "dataset_id": row["dataset_id"],
                "configuration": strict_json(row["configuration"]),
                "summary": strict_json(row["summary"])}

    def items(self, analysis_id, kind, session_id=None):
        with self.connect() as db:
            for row in db.execute("SELECT payload,session_ids FROM items WHERE analysis_id=? AND kind=? ORDER BY id",
                                  (analysis_id, kind)):
                if session_id is None or session_id in strict_json(row["session_ids"]):
                    yield strict_json(row["payload"])

    def put_item(self, db, analysis_id, kind, item):
        db.execute("INSERT INTO items VALUES (?,?,?,?,?)",
                   (analysis_id, kind, item["id"], canonical(item.get("session_ids", [])), canonical(item)))
