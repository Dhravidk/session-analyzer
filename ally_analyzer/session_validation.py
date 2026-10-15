"""Readiness policy and operator-only artifact/fixture interfaces.

None of the functions admitting files or executing checks is exposed through MCP.
A fixture directory separates test files; it is NOT an OS security sandbox.
"""
import hashlib
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import uuid

from .session_scope import exposure, get_run, get_scope, source_record, start_session_investigation
from .util import AnalyzerError, bounded, canonical, digest, strict_json, utc_now

POLICY_VERSION = "readiness-v1"
EXECUTION_TYPES = ("syntax_or_schema", "target_contract", "positive_behavior", "negative_behavior")


def captured_file(path, limit=65536):
    """Hash all captured bytes while bounding the retained output in memory."""
    sha, prefix, size = hashlib.sha256(), bytearray(), 0
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(chunk); size += len(chunk)
            prefix.extend(chunk[:max(0, limit - len(prefix))])
    return bytes(prefix), sha.hexdigest(), size


def admit_artifact(store, path, label, temporal_relation, completeness, version=None):
    if temporal_relation not in ("historical", "current", "proposed") or completeness not in ("complete", "partial"):
        raise AnalyzerError("Specify artifact temporal relation and completeness")
    selected = Path(path).expanduser()
    if selected.is_symlink() or not selected.is_file() or selected.stat().st_size > 2 * 1024 * 1024:
        raise AnalyzerError("Select a regular UTF-8 artifact no larger than 2 MiB, not a symlink")
    raw = selected.read_bytes()
    content = raw.decode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    metadata = {"label": label, "content_sha256": sha, "temporal_relation": temporal_relation,
                "completeness": completeness, "version": version, "bytes": len(raw), "captured_at": utc_now(),
                "origin": "operator_selected_local_snapshot", "origin_path_hash": digest(str(selected.resolve())),
                "historical_applicability": "not_established_by_current_file" if temporal_relation != "historical" else "operator_reported"}
    aid = "artifact_" + digest(metadata)[:24]
    metadata["id"] = aid
    with store.connect() as db:
        db.execute("INSERT INTO artifact_snapshots VALUES (?,?,?)", (aid, canonical(metadata), content))
    return metadata


def revise_scope(store, investigation_id, artifact_ids=None, analysis_id=None):
    old = get_run(store, investigation_id)
    scope = get_scope(store, old)
    return start_session_investigation(store, analysis_id or old["analysis_id"], old["root_session_id"], old["purpose"],
                                      provenance=old["provenance"]["caller_reported"], revision_of=investigation_id,
                                      artifact_ids=sorted(set(scope["artifact_ids"] + (artifact_ids or []))))


def snapshot_fully_exposed(store, run, snapshot_id):
    source = source_record(store, run, snapshot_id)
    if source["kind"] != "artifact" or source["metadata"]["completeness"] != "complete":
        return False
    return any(x["source_id"] == snapshot_id and x["delivered_characters"] == x["total_characters"] and x["total_characters"] > 0
               for x in exposure(store, run["id"])["sources"])


def current_snapshot(store, run, snapshot_id):
    source = source_record(store, run, snapshot_id)
    if source['kind'] != 'artifact' or source['metadata']['temporal_relation'] != 'current':
        return False
    meta = source['metadata']
    alternatives = [source_record(store, run, aid)['metadata'] for aid in get_scope(store, run)['artifact_ids']]
    return not any(a['temporal_relation'] == 'current' and a['origin_path_hash'] == meta['origin_path_hash']
                   and a['captured_at'] > meta['captured_at'] and a['content_sha256'] != meta['content_sha256'] for a in alternatives)


def get_validation_results(store, investigation_id, recommendation_id):
    from .session_investigation import accounting, record_by_id, records
    run = get_run(store, investigation_id)
    saved = record_by_id(store, investigation_id, "recommendation", recommendation_id)
    proposal, binding = saved["recommendation"], saved["proposal_hash"]
    policy = saved.get('policy_version', POLICY_VERSION)
    checks = []
    def check(name, passed, reason, executor="engine_structural"):
        checks.append({"check_type": name, "status": "passed" if passed else "not_run", "reason": reason,
                       "executor": executor, "proposal_hash": binding, "policy_version": policy})
    snapshot = proposal.get("target_snapshot_id")
    target_required = proposal["target_kind"] in ("use_existing_skill", "existing_skill", "new_skill", "claude_md", "hook", "configuration", "code", "verification")
    if target_required:
        complete = bool(snapshot and snapshot_fully_exposed(store, run, snapshot))
        current = bool(snapshot and current_snapshot(store, run, snapshot))
        check("target_inspection", complete and current and any(r["source_id"] == snapshot for r in proposal["target_references"]),
              "Requires a complete, read current target with a proposal reference and no newer different snapshot of that target in scope")
    elif proposal["target_kind"] == "prompt":
        request_ids = {t["request_event_id"] for t in accounting(store, run)["turns"]}
        exposed = {s["source_id"] for s in exposure(store, investigation_id)["sources"] if s["delivered_characters"] == s["total_characters"] and s["total_characters"] > 0}
        check("original_request_inspection", bool({r["source_id"] for r in proposal["target_references"]} & request_ids & exposed),
              "Requires the original user request in the inspected evidence; whether it omitted a requirement is a model judgment")
    else:
        check("target_references", bool(proposal["target_references"]), "Workflow change needs concrete source references")
    review = proposal.get("contextual_review")
    contradicted = bool(review and review["unresolved_material_contradictions"])
    review_ok = bool(review and review["references"] and not contradicted)
    check("contextual_review", review_ok, "Submitted review is attributed to Claude, not independent entailment validation", "caller_model_review")
    if contradicted:
        checks[-1]["status"] = "failed"
    edit_inspection = None
    if policy == 'readiness-v2':
        from .session_diagnostics import get_diagnostic_status, reference_issues
        from .session_edits import INSTRUCTION_TARGETS, inspect_edit
        refs = proposal['target_references'] + (review['references'] if review else [])
        ref_issues = reference_issues(store, run, refs, recommendation_id)
        check('proposal_evidence_inspection', not ref_issues, 'Cited proposal and contextual-review ranges must have been delivered; this does not prove claim support.')
        incident_issues = [i for i in get_diagnostic_status(store, investigation_id)['blocking_issues'] if i.get('record_id') in proposal['incident_ids']]
        check('incident_evidence_inspection', not incident_issues, 'Linked incidents must satisfy their evidence prerequisites: ' + canonical(incident_issues))
        edit_inspection = inspect_edit(store, run, proposal)
        if proposal['target_kind'] in INSTRUCTION_TARGETS:
            instruction = proposal.get('instruction_review')
            edit = proposal.get('edit', {})
            check('exact_instruction_edit', edit_inspection['status'] == 'matched', edit_inspection['reason'])
            allowed_operations = {'use_existing_skill':('invoke',), 'existing_skill':('replace','insert_before','insert_after'),
                                  'new_skill':('create',), 'claude_md':('replace','insert_before','insert_after','create')}
            check('instruction_operation', edit.get('operation') in allowed_operations[proposal['target_kind']], 'Operation must match the declared instruction target.')
            inspected = bool(instruction and all(snapshot_fully_exposed(store, run, sid) and current_snapshot(store, run, sid)
                                                 for sid in instruction['inspected_instruction_ids']))
            if proposal['target_kind'] in ('use_existing_skill','existing_skill') or edit.get('operation') != 'create':
                inspected = inspected and bool(instruction and snapshot in instruction['inspected_instruction_ids'])
            check('instruction_inventory_inspection', inspected, 'Requires fully inspected current snapshots for the declared instruction inventory, including the edited or invoked existing target.')
            scoped = bool(instruction and instruction['scope_references'] and not reference_issues(store, run, instruction['scope_references'], recommendation_id))
            check('instruction_scope_evidence', scoped, 'Scope and applicability need inspected source references.')
            reviewed = bool(instruction and instruction['inventory_status'] == 'complete_for_declared_scope' and instruction['existing_requirement'] != 'unknown')
            check('instruction_overlap_review', reviewed, 'Claude must assess existing requirements, overlap, reuse, alternatives and persistence within a declared complete scope; completeness remains its attributed judgment.', 'caller_model_review')
            ignored_addition = bool(instruction and instruction['existing_requirement'] == 'present_ignored' and edit.get('operation') in ('create','insert_before','insert_after'))
            check('ignored_requirement_not_duplicated', not ignored_addition, 'An ignored existing requirement does not justify appending or creating another instruction; investigate invocation, code, tests or configuration instead.')
            if ignored_addition:
                checks[-1]['status'] = 'failed'
        elif proposal.get('edit'):
            check('exact_proposed_edit', edit_inspection['status'] == 'matched', edit_inspection['reason'])
    quantity_flags = [flag for cid in proposal["claim_ids"] for flag in record_by_id(store, investigation_id, "claim", cid).get("quantity_lint", {}).get("unmeasured_quantity_candidates", [])]
    check("material_quantities", not quantity_flags, "Narrow numeric-unit lint flags require a measured claim revision: " + ", ".join(quantity_flags))
    need_execution = proposal["target_kind"] in ("hook", "configuration", "code", "verification") or proposal["contains_executable_snippet"]
    required = ["syntax_or_schema", "positive_behavior", "negative_behavior"] if need_execution else []
    if proposal["target_kind"] in ("hook", "configuration"):
        required.append("target_contract")
    if need_execution:
        candidate = proposal.get("candidate_snapshot_id")
        check("candidate_snapshot", bool(candidate and source_record(store, run, candidate)["metadata"]["temporal_relation"] == "proposed"
                                           and source_record(store, run, candidate)["metadata"]["completeness"] == "complete"),
              "An executable proposal needs an admitted complete candidate; tests of only the original do not validate the change")
    with store.connect() as db:
        executed = [strict_json(r[0]) for r in db.execute("SELECT payload FROM recommendation_checks WHERE investigation_id=? AND recommendation_id=? AND proposal_hash=? ORDER BY created_at,id", (investigation_id, recommendation_id, binding))]
    for name in required:
        matches = [x for x in executed if x["check_type"] == name]
        # A failure is never hidden by a later success. Revise the proposal or
        # fixture and preserve an explicit operator supersession in a new run.
        if matches:
            status = "failed" if any(x["status"] == "failed" for x in matches) else "passed" if all(x["status"] == "passed" for x in matches) else "unavailable"
            checks.append({"check_type": name, "status": status, "executor": "operator_selected_fixture_runner", "executions": matches})
        else:
            checks.append({"check_type": name, "status": "not_run", "executor": "machine", "reason": "No bound execution evidence. A plan or model assertion is not an executed check."})
    proposal_records = records(store, investigation_id, "recommendation")
    superseded = [x["id"] for x in proposal_records if x["recommendation"].get("revision_of") == recommendation_id]
    if proposal.get("withdrawn_reason"):
        status = "withdrawn"
    elif any(c["status"] != "passed" for c in checks if c["check_type"] in ("target_inspection", "original_request_inspection", "target_references", "proposal_evidence_inspection", "incident_evidence_inspection", "instruction_inventory_inspection", "instruction_scope_evidence")):
        status = "needs_evidence"
    elif not review:
        status = "draft"
    elif any(c["status"] != "passed" for c in checks):
        status = "needs_validation"
    else:
        status = "ready_for_review"
    return {"recommendation_id": recommendation_id, "proposal_hash": binding, "policy_version": policy, "edit_inspection":edit_inspection,
            "status": status, "superseded_by": superseded, "checks": checks, "execution_history": executed,
            "recorded_check_attempt_count": len(executed), "executed_check_count": sum(x.get("exit_code") is not None for x in executed),
            "passed_execution_count": sum(x["status"] == "passed" for x in executed),
            "operator_reviews": [r for r in records(store, investigation_id, 'operator_review') if r['recommendation_id'] == recommendation_id],
            "meaning": "Readiness for review only; not proven benefit, independent semantic validation, acceptance or permission to apply."}


def run_fixture_checks(store, investigation_id, recommendation_id, fixture_dir, plan_path):
    """Explicit operator CLI only; execute reviewed fixture code, never archived commands."""
    from .session_investigation import record_by_id
    run = get_run(store, investigation_id)
    proposal = record_by_id(store, investigation_id, "recommendation", recommendation_id)
    spec = proposal["recommendation"]
    candidate_id = spec.get("candidate_snapshot_id")
    if not candidate_id:
        raise AnalyzerError("A bound proposed candidate snapshot is required")
    candidate = source_record(store, run, candidate_id)
    if candidate["kind"] != "artifact" or candidate["metadata"]["completeness"] != "complete" or candidate["metadata"]["temporal_relation"] != "proposed":
        raise AnalyzerError("Candidate must be a complete operator-admitted proposed artifact")
    selected = Path(fixture_dir).expanduser().resolve(strict=True)
    if not selected.is_dir():
        raise AnalyzerError("Select a reviewed fixture directory")
    plan_raw = Path(plan_path).expanduser().read_bytes()
    plan = strict_json(plan_raw)
    if set(plan) != {"version", "environment", "candidate_filename", "checks"} or not isinstance(plan["checks"], list) or not 1 <= len(plan["checks"]) <= 20:
        raise AnalyzerError("Fixture plan needs version, environment, candidate_filename and 1–20 checks")
    name = plan["candidate_filename"]
    if not isinstance(name, str) or Path(name).name != name or name in (".", ".."):
        raise AnalyzerError("Candidate filename must be a single filename")
    inventory, total = [], 0
    for path in sorted(selected.rglob("*")):
        if path.is_symlink():
            raise AnalyzerError("Fixture directories must not contain symlinks")
        if path.is_file():
            raw = path.read_bytes(); total += len(raw)
            if total > 10 * 1024 * 1024:
                raise AnalyzerError("Fixture directory exceeds 10 MiB")
            inventory.append([str(path.relative_to(selected)), hashlib.sha256(raw).hexdigest()])
    for check in plan["checks"]:
        if set(check) - {"check_type", "argv", "expected_exit", "stdout_contains", "stderr_contains", "stdin", "timeout_seconds"}:
            raise AnalyzerError("Unknown fixture check field")
        if check.get("check_type") not in EXECUTION_TYPES or not isinstance(check.get("argv"), list) or not check["argv"] or not all(isinstance(x, str) for x in check["argv"]):
            raise AnalyzerError("Fixture needs a supported check type and explicit argv")
        if not isinstance(check.get("expected_exit"), int) or isinstance(check["expected_exit"], bool):
            raise AnalyzerError("Fixture expected_exit must be an integer")
        bounded(check.get("timeout_seconds", 10), 1, 60, "timeout_seconds")
        if not any("{candidate}" in x for x in check["argv"]):
            raise AnalyzerError("Each fixture must explicitly consume the bound {candidate}")
    results = []
    # Each check receives a fresh fixture copy to prevent cross-check mutation.
    for check in plan["checks"]:
        with tempfile.TemporaryDirectory(prefix="ally-operator-fixture-") as directory:
            root = Path(directory)
            shutil.copytree(str(selected), str(root / "fixture"))
            working = root / "fixture"
            target = root / name
            target.write_text(candidate["record"]["message"]["content"], encoding="utf-8")
            target.chmod(0o400)
            argv = [x.replace("{candidate}", str(target)) for x in check["argv"]]
            start = time.monotonic(); timed_out = False; launch_error = None; returncode = None
            executable = shutil.which(argv[0]) or argv[0]
            try:
                executable_sha256 = captured_file(Path(executable), limit=0)[1]
            except OSError:
                executable_sha256 = None
            with (root / "stdout").open("wb") as out, (root / "stderr").open("wb") as err:
                try:
                    process = subprocess.Popen(argv, cwd=working, env={"PATH": os.environ.get("PATH", os.defpath), "PYTHONDONTWRITEBYTECODE": "1"},
                                               stdin=subprocess.PIPE, stdout=out, stderr=err, start_new_session=True)
                    try:
                        process.communicate(check.get("stdin", "").encode(), timeout=check.get("timeout_seconds", 10))
                    except subprocess.TimeoutExpired:
                        timed_out = True
                        os.killpg(process.pid, signal.SIGKILL)
                        process.communicate()
                    returncode = process.returncode
                except OSError as exc:
                    launch_error = str(exc)
            stdout, stdout_sha, stdout_bytes = captured_file(root / "stdout")
            stderr, stderr_sha, stderr_bytes = captured_file(root / "stderr")
            truncated = stdout_bytes > 65536 or stderr_bytes > 65536
            try:
                candidate_unchanged = hashlib.sha256(target.read_bytes()).hexdigest() == candidate["metadata"]["content_sha256"]
            except OSError:
                candidate_unchanged = False
            passed = (not launch_error and not timed_out and not truncated and returncode == check["expected_exit"]
                      and check.get("stdout_contains", "").encode() in stdout and check.get("stderr_contains", "").encode() in stderr
                      and candidate_unchanged)
            payload = {"id": "check_" + uuid.uuid4().hex, "check_type": check["check_type"], "check_version": "operator-fixture-v1",
                       "status": "unavailable" if launch_error else "passed" if passed else "failed", "proposal_hash": proposal["proposal_hash"],
                       "candidate_snapshot_id": candidate_id, "candidate_sha256": candidate["metadata"]["content_sha256"],
                       "target_snapshot_id": spec.get("target_snapshot_id"), "scope_id": run["scope_id"],
                       "fixture_hash": digest(inventory), "plan_hash": hashlib.sha256(plan_raw).hexdigest(),
                       "environment": {"operator_description": plan["environment"], "platform": os.uname().sysname,
                                       "executable": executable, "executable_sha256": executable_sha256},
                       "executor": "operator_selected_fixture_runner", "exit_code": returncode, "launch_error": launch_error,
                       "expected_exit": check["expected_exit"], "timed_out": timed_out, "elapsed_seconds": time.monotonic() - start,
                       "stdout": stdout[:65536].decode("utf-8", "replace"), "stderr": stderr[:65536].decode("utf-8", "replace"),
                       "stdout_sha256": stdout_sha, "stderr_sha256": stderr_sha,
                       "stdout_bytes": stdout_bytes, "stderr_bytes": stderr_bytes, "candidate_unchanged": candidate_unchanged,
                       "truncated": truncated, "limitations": "Only this operator-selected fixture and assertions were tested. Temporary directory is not an OS security sandbox."}
            with store.connect() as db:
                db.execute("INSERT INTO recommendation_checks VALUES (?,?,?,?,?,?)", (payload["id"], investigation_id, recommendation_id, proposal["proposal_hash"], canonical(payload), utc_now()))
            results.append(payload)
    return {"executions": results, "validation": get_validation_results(store, investigation_id, recommendation_id)}


def review_recommendation(store, investigation_id, recommendation_id, status, note, check_ids=None):
    """Operator-reported acceptance/outcome; never promotes structural readiness."""
    from .session_investigation import put_record, record_by_id
    allowed = ('accepted', 'dismissed', 'needs_evidence', 'tested_beneficial', 'tested_no_change', 'tested_harmful')
    if status not in allowed or not isinstance(note, str) or not note.strip() or len(note) > 4000:
        raise AnalyzerError('Supply a supported operator status and a nonblank note of at most 4000 characters')
    run = get_run(store, investigation_id)
    proposal = record_by_id(store, investigation_id, 'recommendation', recommendation_id)
    with store.connect() as db:
        for cid in check_ids or []:
            if not db.execute('SELECT 1 FROM recommendation_checks WHERE id=? AND investigation_id=? AND recommendation_id=? AND proposal_hash=?',
                              (cid, investigation_id, recommendation_id, proposal['proposal_hash'])).fetchone():
                raise AnalyzerError('Review check references must be bound to this exact proposal')
    body = {'recommendation_id': recommendation_id, 'proposal_hash': proposal['proposal_hash'], 'status': status, 'note': note,
            'check_ids': check_ids or [], 'executor': 'operator_reported', 'created_at': utc_now(),
            'meaning': 'Operator acceptance or reported outcome is independent of readiness; benefit is not independently certified.'}
    rid = put_record(store, run, 'operator_review', body)
    return {'id':rid, **body}
