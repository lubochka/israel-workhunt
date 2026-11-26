"""Local CV selection and application packets; no transport or submission actions."""
import copy
import hashlib
from pathlib import Path
from records import application_evidence, load, read_store, related_records, save, timestamp
from qualification import brief_from_run, qualify, search_brief, select_search_run
from profile_config import private_root, private_path, safe_output, cv_manifest_path


def select_cv(workdir, language, role):
    root = private_root(workdir)
    profile = load(root / "profile.json", {})
    manifest = load(cv_manifest_path(root, profile), {})
    candidates = [v for v in manifest.get("versions", []) if v.get("language") == language and role in v.get("roles", []) and v.get("selection_status") == "current"]
    if len(candidates) != 1:
        raise ValueError("No unambiguous current CV manifest entry for this language/role")
    cv = copy.deepcopy(candidates[0])
    path = Path(cv["path"])
    if not path.is_absolute():
        path = root / path
    cv["resolved_path"] = str(path)
    measured = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    cv["current_sha256"] = measured
    cv["file_status"] = "unavailable" if measured is None else "hash_matches" if measured == cv.get("sha256") else "changed_since_manifest"
    review = cv.get("content_review") or {}
    cv["content_reviewed"] = bool(measured and measured == cv.get("sha256") and review.get("status") == "reviewed" and review.get("sha256") == measured and review.get("evidence"))
    cv["ready_to_attach"] = cv["file_status"] == "hash_matches" and cv["content_reviewed"] and not cv.get("unresolved_facts")
    cv["readiness_reason"] = "Reviewed file matches the selected version; external action still requires authorization" if cv["ready_to_attach"] else "Missing, changed, unreviewed or unresolved CV; a hash match alone is insufficient"
    return cv


def prepare_packet(workdir, job, review, brief, now, language, role, drafts=None, observed_questions=None, portfolio_evidence=None, authorization=None):
    found, applied = read_store(workdir)
    cv = select_cv(workdir, language, role)
    decision = qualify(job, {**review, "cv_file": cv["resolved_path"]}, brief, now, found, applied)
    return {"schema_version": 1, "opportunity_id": job["id"],
            "identity": {k: job.get(k) for k in ("id", "job_id", "source_job_id", "company", "employer_or_client", "title", "url", "source_url")},
            "prepared_at": now.isoformat(), "preparation_state": "prepared", "submission_state": "not_sent",
            "decision": decision, "cv": cv, "search_brief": copy.deepcopy(brief),
            "drafts": [{**copy.deepcopy(draft), "state": "not_sent"} for draft in drafts or []],
            "form": {"route": copy.deepcopy(review.get("route", {})), "message_field": review.get("route", {}).get("message_field", "unknown"),
                     "observed_questions": copy.deepcopy(observed_questions or []), "unresolved_answers": [q for q in observed_questions or [] if not q.get("answer_evidence")]},
            "portfolio_evidence": copy.deepcopy(portfolio_evidence or []),
            "authorization": copy.deepcopy(authorization or {"scope": "local_preparation", "external_actions_authorized": False}),
            "events": [{"status": "prepared", "at": now.isoformat(), "evidence": "Local application packet prepared; no upload/send performed"}]}


def save_packet(workdir, packet):
    """Only stores local preparation. Submission evidence is a separate canonical record."""
    if packet.get("preparation_state") != "prepared" or packet.get("submission_state") != "not_sent":
        raise ValueError("save_packet only accepts a prepared, unsent packet")
    found, _ = read_store(workdir)
    matches = related_records({"id": packet["opportunity_id"]}, found["opportunities"])
    if len(matches) != 1:
        raise ValueError("Packet must refer to exactly one existing canonical opportunity")
    row = matches[0]
    if row.get("application_packet"):
        row.setdefault("application_packet_history", []).append(row["application_packet"])
    row["application_packet"] = copy.deepcopy(packet)
    # Do not change recommendation, suppression, reported, submission or receipt states.
    found.pop("_history_available", None)
    save(private_root(workdir) / "data/jobs.json", found)


def record_submission_event(workdir, identity, event):
    """Record evidence supplied by an authorized executor; this function never submits."""
    allowed = {"uploaded", "submitted_observed", "receipt_observed", "user_reported_submitted", "historical_claim_only", "response_received"}
    if event.get("status") not in allowed or not event.get("evidence") or not timestamp(event.get("at")):
        raise ValueError("A submission-history event requires a known status, evidence and aware timestamp")
    from datetime import datetime, timezone
    if timestamp(event["at"]) > datetime.now(timezone.utc):
        raise ValueError("Future evidence cannot establish an observed submission")
    if event["status"] in {"uploaded", "submitted_observed"} and not event.get("authorization"):
        raise ValueError("Upload/submission event must retain the direct authorization")
    _, applied = read_store(workdir)
    matches = related_records(identity, applied["records"])
    if len(matches) > 1:
        raise ValueError("Resolve duplicate history identities before recording a submission")
    row = matches[0] if matches else copy.deepcopy(identity)
    if not matches:
        applied["records"].append(row)
    previous = row.get("submission")
    if not isinstance(previous, dict) and ("submission_status" in row or application_evidence(row)["latest"] is not None):
        previous = {key: copy.deepcopy(value) for key, value in row.items()
                    if key not in {"submission", "submission_events", "submission_snapshots"}}
    if isinstance(previous, dict) and previous not in row.setdefault("submission_snapshots", []):
        row["submission_snapshots"].append(copy.deepcopy(previous))
    row.setdefault("submission_events", []).append(copy.deepcopy(event))
    row["submission"] = application_evidence(row)["latest"]
    # Suppression is a separate user/history decision; do not silently change it.
    applied.pop("_history_available", None)
    save(private_root(workdir) / "data/applied_jobs.json", applied)


if __name__ == "__main__":
    import argparse
    import datetime as dt
    import json
    from zoneinfo import ZoneInfo
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "record-event"])
    parser.add_argument("workdir", type=Path)
    parser.add_argument("--input", type=Path, required=True, help="Local evidence/authorization JSON; not a network request")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--save-canonical", action="store_true", help="Persist a prepared packet inside the existing canonical opportunity")
    args = parser.parse_args()
    args.workdir = private_root(args.workdir)
    request_path = private_path(args.workdir, args.input)
    request = load(request_path)
    if args.action == "record-event":
        record_submission_event(args.workdir, request["identity"], request["event"])
        print("Recorded supplied submission-history evidence locally; no external action performed")
    else:
        if not args.output:
            parser.error("prepare requires --output for its local unsent artifact")
        found, _ = read_store(args.workdir)
        matches = related_records({"id": request["opportunity_id"]}, found["opportunities"])
        if len(matches) != 1:
            raise ValueError("Preparation requires one exact existing canonical opportunity")
        profile = load(args.workdir / "profile.json")
        if not profile or not profile.get("timezone"):
            raise ValueError("Packet preparation requires an explicit time zone")
        now = dt.datetime.now(ZoneInfo(profile["timezone"]))
        if "search_brief" in request and "search_run_id" in request:
            raise ValueError("Choose a saved search_run_id or an explicit search_brief, not both")
        if "search_brief" in request:
            snapshot = request["search_brief"]
            if not isinstance(snapshot, dict) or any(timestamp(snapshot.get(key)) is None for key in ("window_start", "window_end")):
                raise ValueError("Explicit search_brief requires full saved, aware window_start and window_end bounds")
        if "search_run_id" in request and (not isinstance(request["search_run_id"], str) or not request["search_run_id"].strip()):
            raise ValueError("Explicit search_run_id must identify a canonical run")
        selected_run = select_search_run(found, request.get("search_run_id")) if "search_brief" not in request else None
        brief = brief_from_run(profile, now, selected_run) if selected_run else search_brief(profile, now, request.get("search_brief"), saved_runs=found.get("search_runs", []))
        packet = prepare_packet(args.workdir, matches[0], request.get("review", matches[0].get("review", {})),
                                brief, now, request["language"], request["role"],
                                request.get("drafts"), request.get("observed_questions"), request.get("portfolio_evidence"), request.get("authorization"))
        if args.output.resolve() in {(args.workdir / "data/jobs.json").resolve(), (args.workdir / "data/applied_jobs.json").resolve()}:
            raise ValueError("Packet output cannot overwrite canonical records")
        args.output = safe_output(args.workdir, args.output, extra_protected=[request_path])
        save(args.output, packet)
        if args.save_canonical:
            save_packet(args.workdir, packet)
        print(json.dumps({"output": str(args.output), "state": "prepared", "submission": "not_sent"}))
