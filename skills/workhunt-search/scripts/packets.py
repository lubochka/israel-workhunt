"""Local CV selection and application packets; no transport or submission actions."""
import copy
import hashlib
from pathlib import Path
from records import load, read_store, related_records, save, timestamp
from qualification import qualify
from profile_config import private_root


def select_cv(workdir, language, role):
    root = private_root(workdir)
    manifest = load(root / "cv-manifest.json", {})
    candidates = [v for v in manifest.get("versions", []) if v.get("language") == language and role in v.get("roles", []) and v.get("selection_status") == "current"]
    if len(candidates) != 1:
        raise ValueError("No unambiguous current CV manifest entry for this language/role")
    cv = copy.deepcopy(candidates[0])
    path = Path(cv["path"])
    if not path.is_absolute():
        path = root / path
    cv["resolved_path"] = str(path)
    cv["content_reviewed"] = False  # Hash/existence do not establish factual reconciliation.
    measured = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    cv["current_sha256"] = measured
    cv["file_status"] = "unavailable" if measured is None else "hash_matches" if measured == cv.get("sha256") else "changed_since_manifest"
    return cv


def prepare_packet(workdir, job, review, brief, now, language, role, drafts=None, observed_questions=None, portfolio_evidence=None, authorization=None):
    found, applied = read_store(workdir)
    cv = select_cv(workdir, language, role)
    decision = qualify(job, {**review, "cv_file": cv["resolved_path"]}, brief, now, found, applied)
    return {"schema_version": 1, "opportunity_id": job["id"],
            "identity": {k: job.get(k) for k in ("id", "job_id", "source_job_id", "company", "employer_or_client", "title", "url", "source_url")},
            "prepared_at": now.isoformat(), "preparation_state": "prepared", "submission_state": "not_sent",
            "decision": decision, "cv": cv,
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
    row.setdefault("submission_events", []).append(copy.deepcopy(event))
    row["submission"] = copy.deepcopy(event)
    # Suppression is a separate user/history decision; do not silently change it.
    applied.pop("_history_available", None)
    save(private_root(workdir) / "data/applied_jobs.json", applied)
