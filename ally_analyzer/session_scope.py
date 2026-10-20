"""Immutable session membership, indexed evidence and audited bounded disclosure."""
import hashlib
import re
import uuid
from collections import Counter, defaultdict, deque

from .engine import get_evidence
from .normalize import ADAPTER_VERSION, KNOWN_TYPES, OBSERVED_VERSIONS, content_blocks, parse_events
from .trajectory import NOTICE, TEXT_VERSION, require_content, trajectory_text
from .util import AnalyzerError, bounded, canonical, digest, strict_json, utc_now

CONTRACT = "single-session-v2"
POLICY = "masked-visible-v1"
GRAPH_VERSION = "recorded-relationships-v1"
RELATIONS = ("parent", "next", "response_frame", "emits_call", "has_result", "delegates", "contains")


def get_run(store, investigation_id):
    with store.connect() as db:
        row = db.execute("SELECT payload FROM session_runs WHERE id=?", (investigation_id,)).fetchone()
    if row is None:
        raise AnalyzerError("Unknown investigation ID")
    return strict_json(row[0])


def get_scope(store, run):
    with store.connect() as db:
        row = db.execute("SELECT payload FROM session_scopes WHERE id=?", (run["scope_id"],)).fetchone()
    return strict_json(row[0])


def scope_rows(store, run):
    scope = get_scope(store, run)
    with store.connect() as db:
        return [dict(r) for r in db.execute("SELECT e.* FROM scope_events s JOIN events e ON e.id=s.event_id AND e.dataset_id=? WHERE s.scope_id=? ORDER BY s.ordinal", (scope["dataset_id"], run["scope_id"]))]


def queued_instruction_metadata(raw):
    """Recognize a structured historical update, never prose claiming user origin."""
    attachment = raw.get('attachment')
    if (raw.get('type') != 'attachment' or not isinstance(attachment, dict)
            or attachment.get('type') != 'queued_command' or attachment.get('commandMode') != 'prompt'
            or not isinstance(attachment.get('prompt'), str) or not attachment['prompt'].strip()):
        return None
    origin = attachment.get('origin')
    human = isinstance(origin, dict) and origin.get('kind') == 'human' and attachment.get('humanTurn') is True
    return {'source_kind': 'queued_command_attachment',
            'origin_basis': 'captured_human_update' if human else 'queued_update_origin_unverified'}


def instruction_updates(store, run):
    """Source inventory separate from reconstructed turns and token accounting."""
    result = []
    for row in scope_rows(store, run):
        if row['agent_id'] != 'main' or row['kind'] != 'attachment':
            continue
        metadata = queued_instruction_metadata(strict_json(row['raw']))
        if metadata:
            result.append({'source_id': row['id'], 'timestamp': row['timestamp'], **metadata})
    return result


def entities(store, run, kind):
    with store.connect() as db:
        return [strict_json(r[0]) for r in db.execute("SELECT payload FROM scope_entities WHERE scope_id=? AND kind=? ORDER BY id", (run["scope_id"], kind))]


def start_session_investigation(store, analysis_id, session_id, purpose, provenance=None,
                                revision_of=None, artifact_ids=None):
    analysis = store.analysis(analysis_id)
    artifacts = sorted(set(artifact_ids or []))
    previous = get_run(store, revision_of) if revision_of else None
    if previous and previous["root_session_id"] != session_id:
        raise AnalyzerError("A scope revision must keep the same root session")
    with store.connect() as db:
        for aid in artifacts:
            if not db.execute("SELECT 1 FROM artifact_snapshots WHERE id=?", (aid,)).fetchone():
                raise AnalyzerError("Artifact must first be admitted by the operator")
        rows = [dict(r) for r in db.execute("SELECT * FROM events WHERE dataset_id=? AND session_id=? ORDER BY COALESCE(timestamp,''),id", (analysis["dataset_id"], session_id))]
    if not rows or not any(r["agent_id"] == "main" for r in rows):
        raise AnalyzerError("The selected session has no captured root agent")
    for row in rows:
        row["record"] = strict_json(row["raw"])
    conflicts = {key for key, count in Counter(r["logical_key"] for r in rows).items() if count > 1}
    for row in rows:
        row["identity_conflict"] = row["logical_key"] in conflicts
    all_data = parse_events(rows)
    available = {r["agent_id"] for r in rows}
    admitted, links = {"main"}, []
    agents = list(store.items(analysis_id, "agent", session_id))
    # Only structured delegation IDs or imported subagent metadata admit a child.
    while True:
        old = set(admitted)
        for tool in all_data["tools"]:
            if not any(a in admitted for s, a in tool["scopes"] if s == session_id):
                continue
            candidates = [(tool.get("child_agent_id"), "tool_result.agentId", tool["evidence"])]
            candidates += [(a["agent_id"], "subagent_metadata.toolUseId", [a.get("metadata_member_id")])
                           for a in agents if a.get("parent_tool_id") == tool["id"]]
            for child, basis, evidence in candidates:
                if not child or child == "main":
                    continue
                link = {"tool_id": tool["id"], "child_agent_id": child, "basis": basis,
                        "source_ids": evidence, "trace_available": child in available}
                if link not in links:
                    links.append(link)
                if child in available:
                    admitted.add(child)
        if old == admitted:
            break
    selected = [r for r in rows if r["agent_id"] in admitted]
    data = parse_events(selected)
    scope = {"contract_version": CONTRACT, "analysis_id": analysis_id, "dataset_id": analysis["dataset_id"],
             "root_session_id": session_id, "agent_ids": sorted(admitted), "event_ids": [r["id"] for r in selected],
             "artifact_ids": artifacts, "delegation_links": links, "adapter_version": ADAPTER_VERSION,
             "graph_version": GRAPH_VERSION, "text_version": TEXT_VERSION, "disclosure_policy": POLICY,
             "source_snapshot_hash": digest([(r["id"], r["payload_hash"]) for r in selected]),
             "excluded_unlinked_agents": sorted(available - admitted)}
    scope_id = "scope_" + digest(scope)[:24]
    scope["id"] = scope_id
    run_id = "investigation_" + uuid.uuid4().hex
    run = {"id": run_id, "scope_id": scope_id, "analysis_id": analysis_id, "root_session_id": session_id,
           "contract_version": CONTRACT, "purpose": purpose, "run_status": "running", "conclusion": None,
           "revision_of": revision_of, "created_at": utc_now(),
           "provenance": {"caller_reported": provenance or {}, "runner_attestation": None},
           "unresolved_questions": [], "analyzer_usage": {"status": "unavailable", "reason": "Host telemetry not yet recorded"}}
    edges, diagnostics = build_graph(selected, data, links)
    scope["capture_gaps"] = {
        "missing_child_traces": [x for x in links if not x["trace_available"]],
        "unlinked_agent_count": len(available - admitted), "graph_diagnostics": diagnostics,
        "unknown_record_types": sorted({r["kind"] for r in selected} - KNOWN_TYPES),
        "unobserved_versions": sorted({r["version"] for r in selected if r["version"]} - OBSERVED_VERSIONS),
        "complete_capture": "not_established", "final_task_outcome": "requires_contextual_investigation"}
    # Diagnostics whose member files contributed to this scope; dataset-wide
    # malformed records with no identifiable session remain explicitly unassigned.
    with store.connect() as db:
        members = {r[0] for r in db.execute("SELECT DISTINCT p.path FROM provenance p JOIN scope_events s ON p.event_id=s.event_id WHERE s.scope_id=? AND p.dataset_id=?", (scope_id, analysis["dataset_id"]))}
        if not members:
            for row in selected:
                members.update(r[0] for r in db.execute("SELECT path FROM provenance WHERE dataset_id=? AND event_id=?", (analysis["dataset_id"], row["id"])))
        diagnostic_rows = list(db.execute("SELECT code,path,line FROM diagnostics WHERE dataset_id=?", (analysis["dataset_id"],)))
        scope["capture_gaps"]["source_diagnostics"] = [{"code": r["code"], "member_id": digest(r["path"])[:16], "line": r["line"]} for r in diagnostic_rows if r["path"] in members]
        scope["capture_gaps"]["unassigned_dataset_diagnostic_count"] = sum(r["path"] not in members for r in diagnostic_rows)
        db.execute("INSERT OR IGNORE INTO session_scopes VALUES (?,?)", (scope_id, canonical(scope)))
        for ordinal, row in enumerate(selected):
            db.execute("INSERT OR IGNORE INTO scope_events VALUES (?,?,?)", (scope_id, row["id"], ordinal))
        for kind, values in (("response", data["responses"]), ("tool", data["tools"]), ("lifecycle", data["lifecycle"])):
            for value in values:
                db.execute("INSERT OR IGNORE INTO scope_entities VALUES (?,?,?,?)", (scope_id, kind, value["id"], canonical(value)))
        for edge in edges:
            db.execute("INSERT OR IGNORE INTO scope_edges VALUES (?,?,?,?,?,?)", (scope_id, edge["id"], edge["source"], edge["target"], edge["relation"], canonical(edge)))
        db.execute("INSERT INTO session_runs VALUES (?,?,?,?,?)", (run_id, analysis_id, scope_id, canonical(run), run["created_at"]))
    return {"investigation": run, "scope": {k: v for k, v in scope.items() if k != "event_ids"}, "event_count": len(selected)}


def build_graph(rows, data, links):
    edges, diagnostics, uuids, by_agent = [], [], defaultdict(list), defaultdict(list)
    by_id = {r["id"]: r for r in rows}
    def add(source, target, relation, refs, basis="recorded"):
        edge = {"source": source, "target": target, "relation": relation, "basis": basis,
                "source_ids": refs, "extractor_version": GRAPH_VERSION}
        edge["id"] = "edge_" + digest(edge)[:24]
        edges.append(edge)
    for row in rows:
        raw = row["record"]
        if isinstance(raw.get("uuid"), str):
            uuids[raw["uuid"]].append(row["id"])
        by_agent[row["agent_id"]].append(row["id"])
        add("agent:" + row["agent_id"], "event:" + row["id"], "contains", [row["id"]])
    parents = {}
    for row in rows:
        parent = row["record"].get("parentUuid")
        if parent:
            matches = uuids.get(parent, [])
            if len(matches) == 1 and matches[0] != row["id"]:
                parents[row["id"]] = matches[0]
                add("event:" + matches[0], "event:" + row["id"], "parent", [row["id"]])
            else:
                diagnostics.append({"code": "ambiguous_or_missing_parent", "event_id": row["id"], "candidate_count": len(matches)})
    # Keep source-recorded cycles; flag them and always bound traversal.
    checked = set()
    for start in parents:
        path, current = set(), start
        while current in parents and current not in checked:
            if current in path:
                diagnostics.append({"code": "parent_cycle", "event_id": current})
                break
            path.add(current); current = parents[current]
        checked.update(path)
    for events in by_agent.values():
        for left, right in zip(events, events[1:]):
            add("event:" + left, "event:" + right, "next", [left, right], "derived_order_not_causality")
    for response in data["responses"]:
        for eid in response["evidence"]:
            add("event:" + eid, "response:" + response["id"], "response_frame", [eid])
    for tool in data["tools"]:
        if tool.get("step_id"):
            add("response:" + tool["step_id"], "tool:" + tool["id"], "emits_call", [tool["evidence_id"]])
        for eid in tool["evidence"]:
            row = by_id[eid]
            if any(b.get("type") == "tool_result" and b.get("tool_use_id") == tool["id"] for b in content_blocks(row["record"])):
                add("tool:" + tool["id"], "event:" + row["id"], "has_result", [row["id"]])
    for link in links:
        if link["trace_available"]:
            add("tool:" + link["tool_id"], "agent:" + link["child_agent_id"], "delegates", link["source_ids"])
    return edges, diagnostics


def source_record(store, run, source_id):
    scope = get_scope(store, run)
    with store.connect() as db:
        if source_id in scope["artifact_ids"]:
            row = db.execute("SELECT payload,content FROM artifact_snapshots WHERE id=?", (source_id,)).fetchone()
            meta = strict_json(row["payload"])
            return {"id": source_id, "kind": "artifact", "payload_hash": meta["content_sha256"],
                    "record": {"message": {"content": row["content"]}}, "metadata": meta}
        row = db.execute("SELECT e.* FROM scope_events s JOIN events e ON e.id=s.event_id AND e.dataset_id=? WHERE s.scope_id=? AND s.event_id=?", (scope["dataset_id"], run["scope_id"], source_id)).fetchone()
    if row is None:
        raise AnalyzerError("Source reference is outside the immutable investigation scope")
    return dict(row, record=strict_json(row["raw"]), metadata=get_evidence(store, scope["dataset_id"], source_id))


def projection(store, run, source_id, scope=None, include_metadata=True, connection=None):
    if connection is None:
        with store.connect() as db:
            return projection(store, run, source_id, scope, include_metadata, db)
    scope = scope or get_scope(store, run)
    db = connection
    artifact = source_id in scope["artifact_ids"]
    if artifact:
        row = db.execute("SELECT payload,content FROM artifact_snapshots WHERE id=?", (source_id,)).fetchone()
        meta = strict_json(row["payload"])
        fingerprint, kind = meta["content_sha256"], "artifact"
    else:
        row = db.execute("SELECT e.payload_hash,e.kind FROM scope_events s JOIN events e ON e.id=s.event_id AND e.dataset_id=? WHERE s.scope_id=? AND s.event_id=?", (scope["dataset_id"], run["scope_id"], source_id)).fetchone()
        if row is None:
            raise AnalyzerError("Source reference is outside the immutable investigation scope")
        fingerprint, kind = row["payload_hash"], row["kind"]
    text_version, policy = scope["text_version"], scope["disclosure_policy"]
    if policy != POLICY:
        raise AnalyzerError("Unsupported retained disclosure policy version")
    key = digest([fingerprint, text_version, policy, kind])
    cached = db.execute("SELECT text,sha256,disclosure FROM evidence_text WHERE cache_key=?", (key,)).fetchone()
    if cached:
        content, sha, disclosure = cached["text"], cached["sha256"], strict_json(cached["disclosure"])
    else:
        if artifact:
            record = {"message": {"content": row["content"]}}
        else:
            raw = db.execute("SELECT raw FROM events WHERE dataset_id=? AND id=?", (scope["dataset_id"], source_id)).fetchone()[0]
            record = strict_json(raw)
        content, disclosure = trajectory_text(record, text_version=text_version)
        sha = hashlib.sha256(content.encode()).hexdigest()
        db.execute("INSERT OR IGNORE INTO evidence_text VALUES (?,?,?,?)", (key, content, sha, canonical(disclosure)))
    metadata = (meta if artifact else get_evidence(store, scope["dataset_id"], source_id)) if include_metadata else None
    return content, sha, disclosure, metadata


def log_access(store, run, operation, request, deliveries=None, error=None):
    scope = get_scope(store, run)
    payload = {"request_id": "access_" + uuid.uuid4().hex, "scope_id": run["scope_id"], "operation": operation,
               "request": request, "deliveries": deliveries or [], "status": "denied_or_failed" if error else "returned",
               "error": error, "text_version": scope["text_version"], "policy": scope["disclosure_policy"],
               "workflow_phase":run.get('review_workflow',{}).get('phase')}
    with store.connect() as db:
        db.execute("INSERT INTO investigation_access(investigation_id,payload,created_at) VALUES (?,?,?)", (run["id"], canonical(payload), utc_now()))
    return payload["request_id"]


def read_investigation_evidence(store, investigation_id, source_id, start_char=0, max_chars=8000,
                                expected_text_sha256=None, allow_content=False):
    run = get_run(store, investigation_id)
    request = {"source_id": source_id, "start_char": start_char, "max_chars": max_chars, "expected_text_sha256": expected_text_sha256}
    try:
        require_content(allow_content)
        bounded(start_char, 0, 100000000, "start_char"); bounded(max_chars, 1, 12000, "max_chars")
        scope = get_scope(store, run)
        text, sha, disclosure, metadata = projection(store, run, source_id, scope=scope)
        if expected_text_sha256 and sha != expected_text_sha256:
            raise AnalyzerError("Text fingerprint mismatch")
        if start_char > len(text):
            raise AnalyzerError("start_char exceeds projected text")
        end = min(len(text), start_char + max_chars)
        delivery = {"source_id": source_id, "text_sha256": sha, "start_char": start_char, "end_char": end,
                    "total_characters": len(text), "access_type": "read", "truncated": start_char > 0 or end < len(text), **disclosure}
        request_id = log_access(store, run, "read", request, [delivery])
        return {"request_id": request_id, "scope_id": run["scope_id"], "evidence": metadata, **delivery,
                "text": text[start_char:end], "text_version": scope["text_version"],
                "next_start_char": end if end < len(text) else None, "untrusted_source_notice": NOTICE}
    except (AnalyzerError, ValueError) as exc:
        log_access(store, run, "read", request, error=str(exc)); raise


def search_investigation_text(store, investigation_id, query, limit=10, scan_offset=0, max_scan=1000, allow_content=False):
    run = get_run(store, investigation_id)
    request = {"query": query, "limit": limit, "scan_offset": scan_offset, "max_scan": max_scan}
    try:
        require_content(allow_content)
        if not isinstance(query, str) or not 2 <= len(query.strip()) <= 200:
            raise AnalyzerError("Literal query must contain 2–200 characters")
        bounded(limit, 1, 50, "limit"); bounded(scan_offset, 0, 10000000, "scan_offset"); bounded(max_scan, 1, 5000, "max_scan")
        scope = get_scope(store, run)
        sources = scope["event_ids"] + scope["artifact_ids"]
        matches, deliveries, scanned = [], [], 0
        pattern = re.compile(re.escape(query.strip()), re.I)
        with store.connect() as db:
            for source_id in sources[scan_offset:scan_offset + max_scan]:
                text, sha, disclosure, _ = projection(store, run, source_id, scope=scope, include_metadata=False, connection=db)
                scanned += 1
                match = pattern.search(text)
                if match:
                    start, end = max(0, match.start() - 100), min(len(text), match.end() + 180)
                    delivery = {"source_id": source_id, "text_sha256": sha, "start_char": start, "end_char": end,
                                "total_characters": len(text), "access_type": "search_snippet", "truncated": start > 0 or end < len(text), **disclosure}
                    deliveries.append(delivery)
                    matches.append(dict(delivery, snippet=text[start:end], match_start_char=match.start()))
                    if len(matches) == limit:
                        break
        next_offset = scan_offset + scanned if scan_offset + scanned < len(sources) else None
        request.update(sources_scanned=scanned, reached_end_of_scope=next_offset is None, next_scan_offset=next_offset)
        request_id = log_access(store, run, "search", request, deliveries)
        return {"request_id": request_id, "scope_id": run["scope_id"], "text_version": scope["text_version"], "matches": matches, "sources_scanned": scanned,
                "scope_sources": len(sources), "next_scan_offset": next_offset, "reached_end_of_scope": next_offset is None,
                "semantics": "literal case-insensitive, first occurrence per source, same query on continuation",
                "limitations": "An empty partial page is not absence. Search snippets are not full reads.", "untrusted_source_notice": NOTICE}
    except (AnalyzerError, ValueError) as exc:
        log_access(store, run, "search", request, error=str(exc)); raise


def read_investigation_batch(store, investigation_id, source_ids, max_chars_per_source=2000, allow_content=False):
    """Reduce round trips without summarizing or removing reread access."""
    run = get_run(store, investigation_id)
    request = {'source_ids':source_ids, 'max_chars_per_source':max_chars_per_source}
    try:
        require_content(allow_content)
        bounded(len(source_ids), 1, 8, 'source_ids count')
        bounded(max_chars_per_source, 1, 3000, 'max_chars_per_source')
        if len(set(source_ids)) != len(source_ids):
            raise AnalyzerError('Batch sources must be unique')
        for source in source_ids:
            source_record(store, run, source)
    except AnalyzerError as exc:
        log_access(store, run, 'batch', request, error=str(exc)); raise
    pages = [read_investigation_evidence(store, investigation_id, source, max_chars=max_chars_per_source, allow_content=allow_content)
             for source in source_ids]
    return {'scope_id':run['scope_id'], 'pages':pages, 'max_text_characters':len(source_ids) * max_chars_per_source,
            'continuation':'Continue each truncated source through read_investigation_evidence with its next_start_char and fingerprint.',
            'untrusted_source_notice':NOTICE}


def get_related_evidence(store, investigation_id, anchor, relations=None, depth=1, limit=30, offset=0):
    run = get_run(store, investigation_id)
    relations = relations or [r for r in RELATIONS if r not in ("next", "contains")]
    request = dict(anchor=anchor, relations=relations, depth=depth, limit=limit, offset=offset)
    try:
        bounded(depth, 1, 6, "depth"); bounded(limit, 1, 100, "limit"); bounded(offset, 0, 10000, "offset")
        if set(relations) - set(RELATIONS):
            raise AnalyzerError("Unsupported recorded relation type")
        scope = get_scope(store, run)
        anchor = "event:" + anchor if anchor in scope["event_ids"] else anchor
        node_kind, separator, node_id = anchor.partition(":")
        with store.connect() as db:
            if node_kind == "event":
                valid = db.execute("SELECT 1 FROM scope_events WHERE scope_id=? AND event_id=?", (run["scope_id"], node_id)).fetchone() is not None
            elif node_kind in ("tool", "response"):
                valid = db.execute("SELECT 1 FROM scope_entities WHERE scope_id=? AND kind=? AND id=?", (run["scope_id"], node_kind, node_id)).fetchone() is not None
            else:
                valid = node_kind == "agent" and node_id in scope["agent_ids"]
        if not separator or not valid:
            raise AnalyzerError("Graph anchor is outside the immutable scope")
        queue, visited, found, expanded = deque([(anchor, 0)]), {anchor}, {}, 0
        depth_limited = False
        with store.connect() as db:
            while queue and expanded < 1000:
                node, level = queue.popleft()
                if level == depth:
                    depth_limited = True; continue
                expanded += 1
                placeholders = ",".join("?" for _ in relations)
                rows = db.execute("SELECT payload FROM scope_edges WHERE scope_id=? AND (source=? OR target=?) AND relation IN (" + placeholders + ") ORDER BY id LIMIT 1001", [run["scope_id"], node, node] + relations).fetchall()
                if len(rows) > 1000:
                    depth_limited = True
                for row in rows[:1000]:
                    edge = strict_json(row[0]); found[edge["id"]] = edge
                    neighbor = edge["target"] if edge["source"] == node else edge["source"]
                    if neighbor not in visited:
                        visited.add(neighbor); queue.append((neighbor, level + 1))
        ordered = sorted(found.values(), key=lambda e: e["id"])
        page = ordered[offset:offset + limit]
        sources = sorted({x[6:] for edge in page for x in (edge["source"], edge["target"]) if x.startswith("event:")})
        rid = log_access(store, run, "graph", request, [{"source_id": x, "access_type": "metadata"} for x in sources])
        return {"request_id": rid, "scope_id": run["scope_id"], "edges": page, "source_ids": sources,
                "next_offset": offset + limit if offset + limit < len(ordered) else None,
                "traversal_limited": bool(queue) or depth_limited, "visited_nodes": len(visited),
                "continuation": "Same anchor/relations/depth with next_offset; expand a returned node for further depth.",
                "limitations": "Recorded and order links are navigation, not causal evidence. Missing paths do not establish absence."}
    except (AnalyzerError, ValueError) as exc:
        log_access(store, run, "graph", request, error=str(exc)); raise


def exposure(store, investigation_id, workflow_phase=None, after_access_id=0):
    with store.connect() as db:
        accesses = [strict_json(r[0]) for r in db.execute("SELECT payload FROM investigation_access WHERE investigation_id=? AND id>? ORDER BY id", (investigation_id, after_access_id))]
    if workflow_phase:
        accesses = [a for a in accesses if a.get('workflow_phase') == workflow_phase]
    return summarize_exposure(accesses)


def summarize_exposure(accesses):
    """Project a captured access snapshot without another database read."""
    ranges, sizes, metadata_ids = defaultdict(list), {}, set()
    failed = 0
    for record in accesses:
        failed += record["status"] != "returned"
        for delivery in record["deliveries"]:
            metadata_ids.add(delivery["source_id"])
            if "text_sha256" not in delivery:
                continue
            key = (delivery["source_id"], delivery["text_sha256"])
            ranges[key].append((delivery["start_char"], delivery["end_char"]))
            sizes[key] = delivery["total_characters"]
    sources = []
    for key, spans in ranges.items():
        merged = []
        for start, end in sorted(spans):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        sources.append({"source_id": key[0], "text_sha256": key[1], "delivered_ranges": merged,
                        "delivered_characters": sum(end - start for start, end in merged), "total_characters": sizes[key]})
    return {"requests": len(accesses), "failed_or_denied_requests": failed, "metadata_sources": len(metadata_ids),
            "sources": sorted(sources, key=lambda x: x["source_id"]), "meaning": "Exposure only; not comprehension or semantic completeness."}
