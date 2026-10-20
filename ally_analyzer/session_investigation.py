"""Scoped attributed records, reproducible measurements and truthful run states."""
from collections import Counter
import re

from .session_contract import CLAIM, INCIDENT, PROPOSAL, SELECTION, FORMULAS
from .session_metrics import VERSION as METRIC_VERSION, session_accounting, token_metrics
from .session_scope import (entities, exposure, get_run, get_scope, log_access, projection, scope_rows, source_record)
from .util import AnalyzerError, bounded, canonical, digest, integer, strict_json, timestamp, utc_now


def validate_payload(value, schema):
    from .mcp import validate
    validate(value, schema)
    def nonblank(item, path=()):
        if isinstance(item, str) and not item.strip() and path[-2:] not in (("edit", "original_text"), ("edit", "replacement_text")):
            raise AnalyzerError("Text fields must not be blank")
        if isinstance(item, dict):
            for key, child in item.items():
                nonblank(child, path + (key,))
        if isinstance(item, list):
            for child in item:
                nonblank(child, path)
    nonblank(value)


def active_run(store, investigation_id):
    run = get_run(store, investigation_id)
    if run["run_status"] not in ("created", "running"):
        raise AnalyzerError("This investigation is frozen. Start a linked revision to change its conclusions.")
    return run


def put_record(store, run, kind, body, *, connection=None):
    """Append unchanged content, optionally inside the caller's transaction."""
    rid = kind + "_" + digest([run["id"], body])[:24]
    values = (run["id"], kind, rid, canonical(body), utc_now())
    if connection is not None:
        connection.execute("INSERT OR IGNORE INTO investigation_records VALUES (?,?,?,?,?)", values)
        return rid
    with store.connect() as db:
        db.execute("INSERT OR IGNORE INTO investigation_records VALUES (?,?,?,?,?)", values)
    return rid


def records(store, investigation_id, kind, *, connection=None):
    if connection is not None:
        return [{"id": row["id"], **strict_json(row["payload"])} for row in connection.execute("SELECT id,payload FROM investigation_records WHERE investigation_id=? AND kind=? ORDER BY created_at,id", (investigation_id, kind))]
    with store.connect() as db:
        return records(store, investigation_id, kind, connection=db)


def record_by_id(store, investigation_id, kind, rid):
    with store.connect() as db:
        row = db.execute("SELECT payload FROM investigation_records WHERE investigation_id=? AND kind=? AND id=?", (investigation_id, kind, rid)).fetchone()
    if row is None:
        raise AnalyzerError("Record reference does not belong to this investigation")
    return {"id": rid, **strict_json(row[0])}


def validate_refs(store, run, refs, require_text=False, reader_facing=True):
    for ref in refs:
        source_record(store, run, ref["source_id"])
        if reader_facing and run.get('review_workflow',{}).get('citation_explanations_version'):
            explanation=ref.get('explanation','')
            if not explanation.strip():
                raise AnalyzerError('Save explanation on each reader-facing citation, including '+ref['source_id']+': a brief sentence saying what this inspected source establishes about the linked claim. A filename or source ID is not an explanation. No report text was changed.')
            if len(explanation)>240:
                raise AnalyzerError('Keep each source explanation within 240 characters, preserving any material qualification. Put detailed reasoning in the linked claim; the renderer will not shorten your sentence.')
        if require_text:
            text, _, _, _ = projection(store, run, ref['source_id'])
            if not text[ref.get('start_char',0):ref.get('end_char',len(text))].strip():
                raise AnalyzerError('An empty or omitted excerpt cannot support a claim. Record identity and usage remain available as metadata; cite nonempty inspected evidence for findings.')
        fields = {"text_sha256", "start_char", "end_char"}
        if fields & set(ref):
            if not fields <= set(ref):
                raise AnalyzerError("Text references need the fingerprint and both range endpoints")
            text, sha, _, _ = projection(store, run, ref["source_id"])
            if ref["text_sha256"] != sha or not 0 <= ref["start_char"] < ref["end_char"] <= len(text):
                raise AnalyzerError("Citation range or text fingerprint is invalid")
        if 'explanation' in ref:
            from .session_diagnostics import inspected_reference
            from .session_consistency import generic_explanation
            if (run.get('review_workflow',{}).get('semantic_consistency_version') or run.get('review_workflow',{}).get('citation_explanations_version')) and generic_explanation(ref['explanation']):
                raise AnalyzerError('Explain what this source establishes about the linked claim; a generic label such as Error text or Denial message is insufficient')
            if '\n' in ref['explanation'] or '\r' in ref['explanation']:
                raise AnalyzerError('Source explanations must be one short sentence, without line breaks')
            if not inspected_reference(store, run, ref):
                raise AnalyzerError('A source explanation needs an inspected cited range or the fully inspected source')


def check_ids(values, allowed, label):
    if len(values) != len(set(values)) or set(values) - set(allowed):
        raise AnalyzerError(label + " must be unique IDs inside this scope")


def accounting(store, run):
    saved = [x for x in entities(store, run, "accounting") if x['id'] == METRIC_VERSION]
    if saved:
        return saved[0]
    result = session_accounting(store, run)
    result["id"] = METRIC_VERSION
    with store.connect() as db:
        db.execute("INSERT OR IGNORE INTO scope_entities VALUES (?,?,?,?)", (run["scope_id"], "accounting", result["id"], canonical(result)))
    return result


def compact_metrics(metrics):
    return {name: {**{k: v for k, v in m.items() if k != "source_ids"}, "source_count": len(m["source_ids"]),
                   "source_preview": m["source_ids"][:5]} for name, m in metrics.items()}


def get_session_overview(store, investigation_id):
    from .session_review import request_coverage
    run = get_run(store, investigation_id)
    scope, metrics = get_scope(store, run), accounting(store, run)
    rows = scope_rows(store, run)
    request_sample = metrics["turns"][:3] + metrics["turns"][-3:]
    landmarks = [{"source_id": t["request_event_id"], "kind": "request", "origin_basis": t["origin_basis"]} for t in request_sample]
    landmarks += [{"source_id": r["id"], "kind": "assistant", "agent_id": r["agent_id"]} for r in [x for x in rows if x['kind'] == 'assistant' and x['agent_id'] == 'main'][-3:]]
    landmarks += [{"source_id": r["id"], "kind": r["kind"], "agent_id": r["agent_id"]} for r in rows[-5:]]
    landmarks = list({x['source_id']: x for x in landmarks}.values())
    tools = entities(store, run, "tool")
    artifacts = [source_record(store, run, aid)["metadata"] for aid in scope["artifact_ids"]]
    request_id = log_access(store, run, "overview", {}, [{"source_id": x["source_id"], "access_type": "metadata"} for x in landmarks])
    from .session_patterns import turn_patterns
    from .session_failures import failure_coverage
    patterns = turn_patterns(metrics["turns"], tools)
    patterns['rows'] = [{k: v for k, v in row.items() if k != 'member_turn_ids'} for row in patterns['rows']]
    patterns.pop('rules_in_precedence_order')
    capture = {k: v for k, v in scope['capture_gaps'].items() if k not in ('graph_diagnostics', 'source_diagnostics')}
    capture['missing_child_trace_count'] = len({x['child_agent_id'] for x in capture['missing_child_traces']})
    for key in ('graph_diagnostics', 'source_diagnostics'):
        capture[key] = {'count': len(scope['capture_gaps'][key]), 'preview': scope['capture_gaps'][key][:5],
                        'continuation': 'get_investigation_records kind=capture_gaps'}
    from .session_cost import compact_cost, source_session_cost
    from .session_readout import developer_readout
    cost = source_session_cost(store, run)
    coverage = request_coverage(store, run)
    coverage = {**coverage, 'unread_request_count': len(coverage['unread_requests']),
                'unread_requests': coverage['unread_requests'][:8]}
    return {"request_id": request_id, "investigation": run, "scope_id": scope["id"], "event_count": len(rows),
            "request_coverage": coverage,
            "source_cost": compact_cost(cost), "session_readout": developer_readout(cost, metrics['session']),
            "session_metrics": compact_metrics(metrics["session"]), "turn_count": len(metrics["turns"]),
            "turn_attribution_coverage": metrics["attribution_coverage"], "turn_patterns": patterns,
            "tool_outcomes": dict(Counter(t["outcome"] for t in tools)), "capture_gaps": capture,
            "subagents":{"captured_agent_ids":[a for a in scope['agent_ids'] if a!='main'],
                         "invocations":[{'tool_id':t['id'],'child_agent_id':t.get('child_agent_id'),'outcome':t['outcome']}
                                        for t in tools if t['name'] in ('Agent','Task')][:20],
                         "continuation":"Page tools for other invocations; get_subagent_details returns child metrics and paged source identities. Scope metrics include captured children, not parent-reported rollups."},
            "failure_explanations":failure_coverage(tools, records(store, investigation_id, 'failure_explanation')),
            "artifacts": artifacts, "landmarks": landmarks, "continuation": "Page events, turns, responses and tools with get_investigation_records. Read requests, apparent successes and the ending.",
            "exposure_summary": {k: v for k, v in exposure(store, run["id"]).items() if k != "sources"},
            "limits": [metrics["limitations"], "Source usage is separate from analyzer usage.", "Counts and patterns do not determine cause, waste or task success."]}


def get_investigation_records(store, investigation_id, kind, limit=20, offset=0, turn_id=None):
    bounded(limit, 1, 200, "limit"); bounded(offset, 0, 10000000, "offset")
    run = get_run(store, investigation_id)
    if kind == "events":
        values = [{k: r[k] for k in ("id", "agent_id", "kind", "timestamp", "payload_hash")} for r in scope_rows(store, run)]
    elif kind == "turns":
        values = [{"id": t["id"], "request_event_id": t["request_event_id"], "origin_basis": t["origin_basis"],
                   "attribution_bases": t["attribution_bases"], "event_count": len(t["event_ids"]),
                   "response_count": len(t["response_ids"]), "tool_count": len(t["tool_ids"]),
                   "metric_version": METRIC_VERSION,
                   "metrics": {k: m['value'] for k, m in t['metrics'].items()},
                   "incomplete_metrics": {k: {key: m[key] for key in ('known', 'eligible', 'known_subtotal')}
                                          for k, m in t['metrics'].items() if m['value'] is None or m['known'] != m['eligible']},
                   "continuation": "Use turn_id with kind=events, responses or tools to page this turn's underlying identities."}
                  for t in accounting(store, run)["turns"]]
    elif kind in ("responses", "tools"):
        values = entities(store, run, kind[:-1] if kind == "responses" else "tool")
    elif kind == "access":
        with store.connect() as db:
            values = [{"id": r["id"], **strict_json(r["payload"])} for r in db.execute("SELECT id,payload FROM investigation_access WHERE investigation_id=? ORDER BY id", (investigation_id,))]
    elif kind == "capture_gaps":
        scope = get_scope(store, run)
        values = [dict(d, category=key) for key in ('graph_diagnostics', 'source_diagnostics') for d in scope['capture_gaps'][key]]
    elif kind == "inquiries":
        values = records(store, investigation_id, "inquiry")
    elif kind in ("incidents", "claims", "measurements", "recommendations", "requirement_maps", "failure_explanations", "review_checks", "conclusion_drafts"):
        values = records(store, investigation_id, kind[:-1])
        if kind == "recommendations":
            from .session_validation import get_validation_results
            values = [dict(v, validation=get_validation_results(store, investigation_id, v["id"])) for v in values]
    else:
        raise AnalyzerError("Unsupported record kind")
    if turn_id:
        turns = {t['id']: t for t in accounting(store, run)['turns']}
        if turn_id not in turns or kind not in ('events', 'responses', 'tools'):
            raise AnalyzerError('turn_id must name a scoped turn and is supported for events, responses or tools')
        field = {'events':'event_ids','responses':'response_ids','tools':'tool_ids'}[kind]
        members = set(turns[turn_id][field])
        values = [v for v in values if v['id'] in members]
    page = values[offset:offset + limit]
    # Trim the page, never the records. Explicit next_offset preserves access to
    # all identities; detailed turn membership is paged through turn_id.
    while len(page) > 1 and len(canonical(page).encode()) > 192000:
        page.pop()
    if page and len(canonical(page).encode()) > 450000:
        raise AnalyzerError('One stored record exceeds the MCP result budget; inspect the local JSON export')
    sources = [x["id"] for x in page] if kind == "events" else sorted({e for x in page for e in x.get("evidence", [])})
    rid = log_access(store, run, "list", dict(kind=kind, limit=limit, offset=offset, turn_id=turn_id), [{"source_id": x, "access_type": "metadata"} for x in sources])
    return {"request_id": rid, "scope_id": run["scope_id"], "items": page, "total": len(values), "returned": len(page),
            "next_offset": offset + len(page) if offset + len(page) < len(values) else None}


def measure_selection(store, investigation_id, formula, selection, opportunity_tool_ids=None):
    run = active_run(store, investigation_id)
    body = _selection_measurement(store, run, formula, selection, opportunity_tool_ids)
    rid = put_record(store, run, "measurement", body)
    return {"id": rid, **body}


def query_measurement(store, investigation_id, formula, selection, opportunity_tool_ids=None):
    """Answer follow-up questions without changing a frozen investigation."""
    run = get_run(store, investigation_id)
    body = _selection_measurement(store, run, formula, selection, opportunity_tool_ids)
    request_id = log_access(store, run, "query_measurement", {
        "formula": formula, "selection": selection, "opportunity_tool_ids": opportunity_tool_ids or []})
    return {"query_id": "query_" + digest([run['scope_id'], body])[:24],
            "request_id": request_id, "investigation_id": run['id'], "scope_id": run['scope_id'],
            "saved_as_claim_evidence": False, **body}


def _selection_measurement(store, run, formula, selection, opportunity_tool_ids=None):
    validate_payload(selection, SELECTION)
    if formula not in FORMULAS:
        raise AnalyzerError("Unknown formula")
    all_responses = {r["id"]: r for r in entities(store, run, "response")}
    all_tools = {t["id"]: t for t in entities(store, run, "tool")}
    all_events = {r["id"]: r for r in scope_rows(store, run)}
    response_ids, tool_ids, event_ids = (selection.get(k, []) for k in ("response_ids", "tool_ids", "event_ids"))
    agent_selection = None
    if selection.get('agent_id') and not (selection.get('turn_id') or selection.get('all_scoped')):
        raise AnalyzerError('agent_id requires turn_id or all_scoped; explicit IDs already define their own population')
    if selection.get('turn_id') or selection.get('all_scoped'):
        if any(selection.get(k) for k in ('response_ids', 'tool_ids', 'event_ids')) or (selection.get('turn_id') and selection.get('all_scoped')):
            raise AnalyzerError('Choose explicit identities, one turn or the entire scope, not a mixture')
        if selection.get('turn_id'):
            selected_turns = [t for t in accounting(store, run)['turns'] if t['id'] == selection['turn_id']]
            if not selected_turns:
                raise AnalyzerError('Selection turn is outside this scope')
            selected = selected_turns[0]
            response_ids, tool_ids, event_ids = (selected[k] for k in ('response_ids','tool_ids','event_ids'))
        else:
            response_ids, tool_ids, event_ids = list(all_responses), list(all_tools), list(all_events)
    if selection.get('agent_id'):
        agent = selection['agent_id']; scope = get_scope(store, run)
        if agent not in scope['agent_ids']:
            if any(link['child_agent_id'] == agent for link in scope['delegation_links']):
                raise AnalyzerError('The selected child trace is unavailable; its usage is unknown, not zero')
            raise AnalyzerError('Agent is outside this immutable scope')
        agent_selection = {'agent_id': agent, 'population': 'Identities assigned exclusively to this captured agent',
                           'shared_response_ids_excluded': [r for r in response_ids if agent in all_responses[r]['agent_ids'] and len(all_responses[r]['agent_ids']) > 1],
                           'shared_tool_ids_excluded': [t for t in tool_ids if agent in all_tools[t]['agent_ids'] and len(all_tools[t]['agent_ids']) > 1],
                           'limitation': 'Shared identities cannot be attributed to this agent; excluded usage is not zero. Captured usage is not complete execution coverage.'}
        response_ids = [r for r in response_ids if all_responses[r]['agent_ids'] == [agent]]
        tool_ids = [t for t in tool_ids if all_tools[t]['agent_ids'] == [agent]]
        event_ids = [e for e in event_ids if all_events[e]['agent_id'] == agent]
        if opportunity_tool_ids and any(all_tools.get(t, {}).get('agent_ids') != [agent] for t in opportunity_tool_ids):
            raise AnalyzerError('Opportunity population must use identities assigned exclusively to the selected agent')
    for values, allowed, label in ((response_ids, all_responses, "response_ids"), (tool_ids, all_tools, "tool_ids"), (event_ids, all_events, "event_ids")):
        check_ids(values, allowed, label)
    responses, tools = [all_responses[x] for x in response_ids], [all_tools[x] for x in tool_ids]
    known = eligible = 0; unit = "count"; value = subtotal = None; refs = []; extra = {}
    if formula in ("prompt_tokens", "cached_tokens", "completion_tokens", "uncached_input_tokens", "cache_creation_tokens", "peak_input_tokens", "cache_read_share"):
        if not response_ids:
            raise AnalyzerError("Token measurement needs explicit response_ids; tool usage is not allocated automatically")
        if formula in ('peak_input_tokens','cache_read_share'):
            from .session_resources import response_measure
            m=response_measure(formula,responses)
            extra={k:v for k,v in m.items() if k not in ('value','known_subtotal','known','eligible','unit','source_ids')}
        else: m = token_metrics(responses)[formula]
        value, subtotal, known, eligible, unit, refs = (m[k] for k in ("value", "known_subtotal", "known", "eligible", "unit", "source_ids"))
    elif formula in ('input_change_tokens','cache_read_share_change_pp','recorded_compaction_duration_ms'):
        from .session_resources import boundary_measure
        m=boundary_measure(store,run,formula,responses,event_ids)
        value, subtotal, known, eligible, unit, refs = (m[k] for k in ('value','known_subtotal','known','eligible','unit','source_ids'))
        extra={k:v for k,v in m.items() if k not in ('value','known_subtotal','known','eligible','unit','source_ids')}
    elif formula == 'captured_tool_result_bytes':
        from .session_resources import tool_measure
        m=tool_measure(formula,tools)
        value, subtotal, known, eligible, unit, refs = (m[k] for k in ('value','known_subtotal','known','eligible','unit','source_ids'))
        extra={k:v for k,v in m.items() if k not in ('value','known_subtotal','known','eligible','unit','source_ids')}
    elif formula == "response_count":
        value = subtotal = known = eligible = sum(r["eligible"] for r in responses)
        refs = [e for r in responses for e in r["evidence"]]
    elif formula in ("tool_invocations", "tool_failures", "recorded_tool_duration_ms", "occurrence_rate"):
        requested = [t for t in tools if t["requested"]]
        refs = [e for t in tools for e in t["evidence"]]
        eligible = len(tools); known = eligible
        if formula == "tool_invocations":
            value = subtotal = len(requested)
        elif formula == "tool_failures":
            known = sum(t["outcome"] not in ("unresolved", "conflict", "unknown") for t in tools)
            subtotal = sum(t["outcome"] in ("execution_failure", "verification_command_failure", "timeout") for t in tools)
            value = subtotal if known == eligible else None
        elif formula == "recorded_tool_duration_ms":
            valid = [t for t in tools if integer(t.get("recorded_duration_ms")) and not t["warnings"]]
            known = len(valid); subtotal = sum(t["recorded_duration_ms"] for t in valid)
            value = subtotal if known == eligible and eligible else None; unit = "ms"
        else:
            opportunities = opportunity_tool_ids or []
            check_ids(opportunities, all_tools, "opportunity_tool_ids")
            if set(tool_ids) - set(opportunities) or any(not all_tools[t]["requested"] for t in opportunities):
                raise AnalyzerError("Occurrences must be a subset of the explicit requested-tool opportunity population")
            eligible = known = len(opportunities); value = subtotal = len(requested) / eligible if eligible else None; unit = "ratio"
            refs += [e for t in opportunities for e in all_tools[t]["evidence"]]
    elif formula == "elapsed_seconds":
        if len(event_ids) != 2:
            raise AnalyzerError("elapsed_seconds needs exactly two explicit ordered endpoint event_ids")
        start, end = [timestamp(all_events[x]["timestamp"]) for x in event_ids]
        eligible = 2; known = sum(x is not None for x in (start, end)); unit = "seconds"; refs = event_ids
        value = subtotal = end - start if known == 2 and end >= start else None
    body = {**extra, "formula": formula, "formula_version": "selection-v3" if agent_selection else "selection-v2", "selection": selection,
            "selection_hash": digest({'scope_id':run['scope_id'], 'response_ids':sorted(response_ids),'tool_ids':sorted(tool_ids),'event_ids':event_ids}),
            "resolved_identity_counts": {'responses':len(response_ids),'tools':len(tool_ids),'events':len(event_ids)},
            "resolved_identities": {'response_ids':sorted(response_ids),'tool_ids':sorted(tool_ids),'event_ids':event_ids},
            "opportunity_tool_ids": opportunity_tool_ids or [], "value": value, "known_subtotal": subtotal, "unit": unit,
            "known": known, "eligible": eligible, "source_ids": sorted(set(refs)),
            "unavailable_reason": "Missing or conflicting required observations, invalid interval or zero denominator" if value is None else None,
            "deduplication": "unique reconciled identities in this immutable scope", "membership_relevance": "caller interpretation, not engine-verified",
            "non_additive": True, "limitations": "Selections may overlap. Use union identities for totals. Associated usage or an interval is not avoidable overhead."}
    if agent_selection:
        body['agent_selection'] = agent_selection
    return body


def save_incident(store, investigation_id, incident):
    run = active_run(store, investigation_id)
    validate_payload(incident, INCIDENT)
    if incident['expectedness']=='expected' and run.get('review_workflow',{}).get('semantic_consistency_version'):
        basis=incident.get('expectedness_basis')
        if not basis:
            raise AnalyzerError('Expected requires expectedness_basis with inspected evidence of an intentional negative check or correct policy enforcement. Common, harmless or recovered errors are not automatically expected; use unexpected or unclear when appropriate. No recommendation is required for either.')
        from .session_requirements import inspected_refs
        inspected_refs(store,run,basis['references'])
    if incident.get('revision_of'):
        from .session_review import active_versions
        if incident['revision_of'] not in {v['id'] for v in active_versions(records(store,investigation_id,'incident'),'incident')}:
            raise AnalyzerError('An incident revision must name its current version in this investigation')
    scope = get_scope(store, run)
    check_ids(incident["member_event_ids"], scope["event_ids"], "member_event_ids")
    check_ids(incident["tool_ids"], [t["id"] for t in entities(store, run, "tool")], "tool_ids")
    if not incident["member_event_ids"]:
        raise AnalyzerError("An incident needs explicit source event membership")
    for field in ("task_references", "recovery_references", "counterevidence"):
        validate_refs(store, run, incident[field])
    if incident["resolution"] == "recovered" and not incident["recovery_references"]:
        raise AnalyzerError("A recovered classification needs recovery evidence")
    claims = []
    for claim in incident["claims"]:
        if run["contract_version"] == "single-session-v2" and "subject" not in claim:
            raise AnalyzerError("Claims in v2 need a subject: distinguish task outcome from reported statement, diagnosis or instruction")
        validate_refs(store, run, claim["references"], require_text=True)
        if claim["evidence_class"] != "proposed_benefit" and not claim["references"]:
            raise AnalyzerError("Factual and interpretive claims require supporting source references")
        if claim["evidence_class"] == "calculated" and "measurement_id" not in claim:
            raise AnalyzerError("Calculated claims require a registered measurement")
        if "expected_value" in claim and "measurement_id" not in claim:
            raise AnalyzerError("Structured numerical claims require a measurement")
        if "measurement_id" in claim:
            measurement = record_by_id(store, investigation_id, "measurement", claim["measurement_id"])
            if "expected_value" in claim and measurement.get("value") != claim["expected_value"]:
                raise AnalyzerError("Structured claim differs from the selected engine measurement")
        claims.append(claim)
    from .session_episodes import validate_episode, validate_attribution
    episode_checks=validate_episode(store,run,incident)
    attribution_checks=validate_attribution(store,run,incident)
    from .session_story import validate_reader_guide
    validate_reader_guide(store,run,incident)
    if incident.get('evidence_links'):
        from .session_requirements import inspected_refs
        from .session_finding_links import incident_episodes
        allowed=set(incident['member_event_ids']) | {r['source_id'] for r in incident['task_references']+incident['recovery_references']+incident['counterevidence']}
        allowed |= {r['source_id'] for c in claims for r in c['references']}
        allowed |= {r['source_id'] for r in incident.get('pattern',{}).get('references',[])}
        for _,episode,_ in incident_episodes(incident):
            allowed |= {r['source_id'] for r in episode['goal_references']}
            allowed |= {r['source_id'] for v in episode['verification'] for r in v['references']}
        for link in incident['evidence_links']:
            if any(r['source_id'] not in allowed for r in link['references']):
                raise AnalyzerError('Evidence relationships must reference explicit finding members or citations')
            validate_refs(store,run,link['references'],require_text=True)
            inspected_refs(store,run,link['references'])
    # Validate the complete submission before saving any of its components.
    claim_ids = []
    for claim in claims:
        flags = re.findall(r"\b\d[\d,.]*\s*(?:tokens?|calls?|attempts?|failures?|seconds?|minutes?|hours?|milliseconds?|%)\b", claim["text"], re.I)
        lint = {"unmeasured_quantity_candidates": flags if "measurement_id" not in claim and claim["evidence_class"] != "participant_statement" else [],
                "limitations": "Narrow numeric-unit lint, not complete detection or semantic validation"}
        claim_ids.append(put_record(store, run, "claim", {"claim": claim, "provenance": incident["provenance"],
                         "support_validation": "caller_model_review_not_engine_entailment", "quantity_lint": lint}))
    body = {"incident": incident, "claim_ids": claim_ids, "classification_basis": "caller_model_interpretation", "reference_validation": "scope_and_ranges_checked"}
    if episode_checks: body['episode_prerequisites']=episode_checks
    if attribution_checks: body['attribution_prerequisites']=attribution_checks
    rid = put_record(store, run, "incident", body)
    return {"id": rid, **body}


def save_recommendation(store, investigation_id, recommendation):
    run = active_run(store, investigation_id)
    validate_payload(recommendation, PROPOSAL)
    for kind, field in (("incident", "incident_ids"), ("claim", "claim_ids")):
        for rid in recommendation[field]:
            record_by_id(store, investigation_id, kind, rid)
    if run['contract_version'] == 'single-session-v2':
        linked_claims = {cid for iid in recommendation['incident_ids']
                         for cid in record_by_id(store, investigation_id, 'incident', iid)['claim_ids']}
        if set(recommendation['claim_ids']) - linked_claims:
            raise AnalyzerError('Recommendation claims must belong to its linked incidents')
    validate_refs(store, run, recommendation["target_references"])
    for field in ("target_snapshot_id", "candidate_snapshot_id"):
        if field in recommendation and recommendation[field] not in get_scope(store, run)["artifact_ids"]:
            raise AnalyzerError("Proposal snapshots must be admitted in this immutable scope")
    if "contextual_review" in recommendation:
        validate_refs(store, run, recommendation["contextual_review"]["references"])
    if "instruction_review" in recommendation:
        review = recommendation["instruction_review"]
        validate_refs(store, run, review["scope_references"])
        check_ids(review["inspected_instruction_ids"], get_scope(store, run)["artifact_ids"], "inspected_instruction_ids")
    if "edit" in recommendation:
        from .session_edits import validate_edit_shape
        validate_edit_shape(recommendation["edit"])
    if recommendation.get("revision_of"):
        record_by_id(store, investigation_id, "recommendation", recommendation["revision_of"])
    body = {"recommendation": recommendation, "proposal_hash": digest(recommendation),
            "policy_version": "readiness-v2" if run["contract_version"] == "single-session-v2" else "readiness-v1"}
    rid = put_record(store, run, "recommendation", body)
    from .session_validation import get_validation_results
    return {"id": rid, **body, "validation": get_validation_results(store, investigation_id, rid)}


def finish_investigation(store, investigation_id, run_status, conclusion, summary, coverage_explanation, unresolved_questions, stop_reason,
                         title=None, observed_outcome=None, stop_basis=None, synopsis=None):
    run = active_run(store, investigation_id)
    if run_status not in ("completed", "partial", "failed") or conclusion not in ("findings", "no_action_supported", "insufficient_evidence"):
        raise AnalyzerError("Invalid investigation status or conclusion")
    if not all(isinstance(x, str) and x.strip() for x in (summary, coverage_explanation, stop_reason)):
        raise AnalyzerError("Conclusion needs nonblank summary, coverage explanation and stop reason")
    if (run_status != "completed" or conclusion == "insufficient_evidence") and not unresolved_questions:
        raise AnalyzerError("Partial, failed or insufficient-evidence investigations must preserve an unresolved question")
    if conclusion == "findings" and not records(store, investigation_id, "incident"):
        raise AnalyzerError("A findings conclusion needs at least one saved incident")
    if conclusion == "no_action_supported":
        proposals = records(store, investigation_id, "recommendation")
        if any(not p["recommendation"].get("withdrawn_reason") and not any(x["recommendation"].get("revision_of") == p["id"] for x in proposals) for p in proposals):
            raise AnalyzerError("Withdraw pending recommendations or use a findings conclusion")
    if run["contract_version"] == "single-session-v2":
        from .session_contract import OUTCOME, SYNOPSIS
        from .session_diagnostics import get_diagnostic_status, outcome_issues, reference_issues, coverage_assertions
        if not title or not observed_outcome or not stop_basis or not synopsis:
            raise AnalyzerError("v2 needs title, synopsis, observed_outcome and stop_basis. Write a 1–3 sentence synopsis of user intent and recorded work; preserve uncertainty.")
        validate_payload(synopsis, SYNOPSIS)
        validate_refs(store, run, synopsis["references"])
        if not synopsis["references"] and not synopsis["limitations"]:
            raise AnalyzerError("A synopsis needs evidence references or an explicit coverage limitation")
        validate_payload(observed_outcome, OUTCOME)
        validate_refs(store, run, observed_outcome["references"])
        if stop_basis not in ("inquiry_answered", "evidence_unavailable", "external_limit", "operator_stop", "investigator_choice"):
            raise AnalyzerError("Unsupported stop_basis")
        diagnostics = get_diagnostic_status(store, investigation_id)
        diagnostics["blocking_issues"] += outcome_issues(store, run, observed_outcome)
        diagnostics["blocking_issues"] += reference_issues(store, run, synopsis["references"], "synopsis")
        diagnostics['coverage_checks'] = coverage_assertions(get_scope(store,run), {'synopsis':synopsis,'observed_outcome':observed_outcome,'summary':summary,'coverage_explanation':coverage_explanation})
        diagnostics['blocking_issues'] += [{'code':'coverage_count_needs_review','record_id':c['field'],'reason':canonical(c)}
                                           for c in diagnostics['coverage_checks'] if c['status']!='passed']
        if run.get('review_workflow'):
            from .session_review import review_checkpoint
            candidate = dict(run_status=run_status, conclusion=conclusion, summary=summary, coverage_explanation=coverage_explanation,
                             unresolved_questions=unresolved_questions, stop_reason=stop_reason, title=title, synopsis=synopsis,
                             observed_outcome=observed_outcome, stop_basis=stop_basis)
            pending = review_checkpoint(store, run, candidate, diagnostics)
            if pending:
                return pending
        if run_status == "completed" and diagnostics["blocking_issues"]:
            raise AnalyzerError("Investigation prerequisites remain open. Use get_diagnostic_status, inspect the available evidence or preserve a partial run; do not relabel supported claims to bypass review. " + canonical(diagnostics["blocking_issues"][:8]))
        run.update(title=title, synopsis=synopsis, observed_outcome=observed_outcome, stop_basis=stop_basis, diagnostic_review=diagnostics)
    run.update(run_status=run_status, conclusion=conclusion, summary=summary, coverage_explanation=coverage_explanation,
               unresolved_questions=unresolved_questions, stop_reason=stop_reason, finished_at=utc_now())
    with store.connect() as db:
        db.execute("UPDATE session_runs SET payload=? WHERE id=?", (canonical(run), investigation_id))
    return {"investigation": run, "exposure": exposure(store, investigation_id), "meaning": "Completed means the declared inquiry ended, not that all evidence was read or all problems ruled out."}
