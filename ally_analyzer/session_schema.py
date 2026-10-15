"""Additive schema: canonical accounting and legacy insight rows stay intact."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS session_runs (
 id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, scope_id TEXT NOT NULL,
 payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS session_scopes (
 id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scope_events (
 scope_id TEXT NOT NULL, event_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
 PRIMARY KEY(scope_id,event_id));
CREATE INDEX IF NOT EXISTS scope_event_order ON scope_events(scope_id,ordinal);
CREATE TABLE IF NOT EXISTS scope_entities (
 scope_id TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(scope_id,kind,id));
CREATE TABLE IF NOT EXISTS scope_edges (
 scope_id TEXT NOT NULL, id TEXT NOT NULL, source TEXT NOT NULL, target TEXT NOT NULL,
 relation TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(scope_id,id));
CREATE INDEX IF NOT EXISTS scope_edges_forward ON scope_edges(scope_id,source,relation);
CREATE INDEX IF NOT EXISTS scope_edges_reverse ON scope_edges(scope_id,target,relation);
CREATE TABLE IF NOT EXISTS evidence_text (
 cache_key TEXT PRIMARY KEY, text TEXT NOT NULL, sha256 TEXT NOT NULL, disclosure TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS investigation_access (
 id INTEGER PRIMARY KEY AUTOINCREMENT, investigation_id TEXT NOT NULL,
 payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS investigation_access_run ON investigation_access(investigation_id,id);
CREATE TABLE IF NOT EXISTS investigation_records (
 investigation_id TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL,
 payload TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(investigation_id,kind,id));
CREATE TABLE IF NOT EXISTS artifact_snapshots (
 id TEXT PRIMARY KEY, payload TEXT NOT NULL, content TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS recommendation_checks (
 id TEXT PRIMARY KEY, investigation_id TEXT NOT NULL, recommendation_id TEXT NOT NULL,
 proposal_hash TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS recommendation_checks_proposal
 ON recommendation_checks(investigation_id,recommendation_id,proposal_hash);
"""
