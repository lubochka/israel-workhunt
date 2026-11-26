"""Canonical opportunity/history storage. Legacy records are read-only inputs."""
import copy
import datetime as dt
import json
from pathlib import Path
import re
import urllib.parse as up
from profile_config import private_root


def load(path, default=None):
    return json.loads(Path(path).read_text(encoding="utf-8-sig")) if Path(path).exists() else copy.deepcopy(default)


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def url_identity(value):
    p = up.urlsplit(str(value or ""))
    if p.scheme not in {"http", "https"} or not p.hostname or p.username:
        return ""
    host = p.hostname.lower().removeprefix("www.")
    path = p.path.rstrip("/")
    # Drushim's trailing page hash is not the requisition identity.
    if host == "drushim.co.il":
        match = re.match(r"/job/(\d+)", path)
        if match:
            path = "/job/" + match[1]
    query = [(k, v) for k, v in up.parse_qsl(p.query) if not k.lower().startswith("utm_") and k.lower() not in {"gclid", "fbclid"}]
    return host + path + ("?" + up.urlencode(sorted(query)) if query else "")


def identity_keys(row):
    keys = set()
    for name in ("id", "canonical_opportunity_id", "canonical_recommendation_id"):
        if row.get(name):
            keys.add(("id", norm(row[name])))
    employers = {norm(row.get("employer_or_client") or row.get("company"))}
    for alias in row.get("identity_aliases", []):
        if isinstance(alias, str) and not url_identity(alias):
            employers.add(norm(alias))
        elif isinstance(alias, dict):
            keys.update(identity_keys(alias))
    employers.discard("")
    job_ids = {norm(row.get(k)) for k in ("job_id", "source_job_id", "employer_requisition_id")}
    job_ids.discard("")
    # Provider IDs are scoped to a board/employer, never globally matched alone.
    for employer in employers:
        for job_id in job_ids:
            keys.add(("employer_id", employer, job_id))
    for job_id in job_ids:
        if row.get("board_key"):
            keys.add(("board_id", norm(row["board_key"]), job_id))
    for name in ("url", "source_url", "canonical_project_url"):
        if url_identity(row.get(name)):
            keys.add(("url", url_identity(row[name])))
    for name in ("source_aliases", "aliases", "identity_aliases", "related_source_ids"):
        for alias in row.get(name, []):
            if isinstance(alias, dict):
                keys.update(identity_keys(alias))
            elif isinstance(alias, str):
                if url_identity(alias):
                    keys.add(("url", url_identity(alias)))
                elif name in {"aliases", "related_source_ids"}:
                    keys.add(("id", norm(alias)))
    return keys


def read_store(workdir):
    workdir = private_root(workdir)
    found = load(workdir / "data/jobs.json", {"schema_version": 1, "search_runs": [], "opportunities": []})
    applied = load(workdir / "data/applied_jobs.json", {"schema_version": 1, "records": [], "unresolved_mentions": []})
    found["_history_available"] = (workdir / "data/jobs.json").is_file()
    applied["_history_available"] = (workdir / "data/applied_jobs.json").is_file()
    return found, applied


def related_records(job, records):
    # Follow explicit alias links transitively, including supplier cross-post IDs.
    keys = identity_keys(job)
    matches, remaining = [], list(records)
    while True:
        found = [r for r in remaining if keys & identity_keys(r)]
        if not found:
            return matches
        for row in found:
            keys.update(identity_keys(row))
            matches.append(row)
            remaining.remove(row)


def identity_groups(rows):
    """Connected identity components; compute each record's keys once."""
    rows = list(rows)
    parents = list(range(len(rows)))
    owners = {}
    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index
    for index, row in enumerate(rows):
        for key in identity_keys(row):
            if key in owners:
                parents[root(index)] = root(owners[key])
            else:
                owners[key] = index
    grouped = {}
    for index, row in enumerate(rows):
        grouped.setdefault(root(index), []).append(row)
    return list(grouped.values())


class IdentityLookup:
    def __init__(self, rows):
        self.groups = identity_groups(rows)
        self.keys = {}
        for index, group in enumerate(self.groups):
            for row in group:
                for key in identity_keys(row):
                    self.keys[key] = index

    def related(self, row):
        indexes = {self.keys[key] for key in identity_keys(row) if key in self.keys}
        return [item for index in sorted(indexes) for item in self.groups[index]]


def history_decision(job, found, applied, index=None):
    rows = index.related(job) if index is not None else related_records(job, found.get("opportunities", []) + applied.get("records", []))
    suppressed, reported, possible, submitted, unresolved = [], [], [], [], []
    for row in rows:
        history = row.get("history") if isinstance(row.get("history"), dict) else {}
        if row.get("suppress_from_new_results") is True or history.get("suppress_from_new_results") is True or history.get("suppress_repeat_recommendation") is True or row.get("status") == "suppressed":
            suppressed.append(row.get("id"))
        if row.get("reported_at") or history.get("reported_at") or history.get("previous_report_time") or history.get("reported_in_chat") is True or history.get("previously_presented_in_chat") is True or row.get("status") == "previously_reported":
            reported.append(row.get("id"))
        if row.get("possible_duplicate_ids") or history.get("decision") == "possible_duplicate" or row.get("status") == "possible_duplicate":
            possible.append(row.get("id"))
        if application_state(row) in {"submitted_observed", "receipt_observed", "user_reported_submitted", "response_received", "platform_verified_historical_application"}:
            submitted.append(row.get("id"))
        if history.get("decision") in {"unresolved", "needs_clarification"} or history.get("newness_qualified") is False:
            unresolved.append(row.get("id"))
    state = "suppressed" if suppressed else "already_applied" if submitted else "previously_reported" if reported else "possible_duplicate" if possible else "unresolved" if unresolved else "new"
    return {"state": state, "matched_ids": list(dict.fromkeys(r.get("id") for r in rows)), "newness_qualified": state == "new"}


def display_job(row):
    result = copy.deepcopy(row)
    for target, source in [("company", "employer_or_client"), ("url", "source_url"), ("job_id", "source_job_id"), ("work_model_stated", "work_mode")]:
        result.setdefault(target, row.get(source, ""))
    result.setdefault("description", "")
    result.setdefault("tracks", [])
    result["saved_decision"] = {k: copy.deepcopy(row[k]) for k in ("status", "qualified", "fit", "decision_reason", "decision_reasons", "reason", "reasons", "history") if k in row}
    if isinstance(result.get("location"), dict):
        result["location"] = " | ".join(str(v) for v in result["location"].values() if isinstance(v, (str, int, float)))
    return result


def merge_discovery(found, jobs, run):
    """Merge discoveries, preserving all assessment/submission data and provenance."""
    result = copy.deepcopy(found)
    result.pop("_history_available", None)
    result.setdefault("opportunities", [])
    existing_ids = {id(row) for row in result["opportunities"]}
    for group in identity_groups(result["opportunities"] + list(jobs)):
        existing = [row for row in group if id(row) in existing_ids]
        incoming = [row for row in group if id(row) not in existing_ids]
        if not incoming:
            continue
        if existing:
            row = existing[0]
        else:
            row = copy.deepcopy(incoming.pop(0))
            result["opportunities"].append(row)
        for job in incoming:
            row.setdefault("observations", []).append(copy.deepcopy(job))
            row.setdefault("source_aliases", [])
            for alias in (job.get("url"), {"id": job["id"]}):
                if alias and alias not in row["source_aliases"]:
                    row["source_aliases"].append(alias)
    result.setdefault("search_runs", []).append(copy.deepcopy(run))
    result["updated_at"] = run["checked_at"]
    return result


def timestamp(value):
    try:
        result = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result if result.tzinfo else None
    except (ValueError, TypeError):
        return None


def application_state(record, now=None):
    if not record:
        return "not_recorded"
    now = now or dt.datetime.now(dt.timezone.utc)
    record = record.get("submission", record)
    status = record.get("submission_status", record.get("status", "unknown"))
    status = {"user_reported_applied": "user_reported_submitted", "not_applied": "not_recorded"}.get(status, status)
    allowed = {"not_recorded", "prepared", "uploaded", "submitted_observed", "receipt_observed", "user_reported_submitted", "historical_claim_only", "response_received", "platform_verified_historical_application"}
    if status not in allowed:
        return "unknown"
    at = timestamp(record.get("at") or record.get("submitted_at"))
    if status in {"submitted_observed", "receipt_observed", "response_received"} and (not record.get("evidence") or not at or at > now):
        return "unverified_submission_claim"
    return status
