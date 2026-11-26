"""Read-only source outcome report from saved canonical evidence; no fresh job verification."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.parse as up
from zoneinfo import ZoneInfo
from qualification import route_evidence_recorded
from profile_config import private_root, safe_output
from records import application_evidence, application_state, history_decision, identity_groups, load, timestamp


def source_labels(row):
    result = set()
    source = row.get("source")
    if isinstance(source, dict):
        source = source.get("name") or source.get("provider")
    if isinstance(source, str) and source:
        result.add(source.casefold())
    if row.get("board_key"):
        result.add(str(row["board_key"]).split(":")[0].casefold())
        result.discard("public_ats")
    if not result:
        host = up.urlsplit(str(row.get("url") or row.get("source_url") or "")).hostname
        if host:
            result.add(host.removeprefix("www."))
    for key in ("discovery_sources", "source_aliases", "observations"):
        for item in row.get(key, []) or []:
            if isinstance(item, dict):
                result.update(source_labels(item))
            elif isinstance(item, str) and "://" in item:
                host = up.urlsplit(item).hostname
                if host:
                    result.add(host.removeprefix("www."))
    aliases = {"drushim.co.il": "drushim", "jobmaster.co.il": "jobmaster", "jobnet.co.il": "jobnet", "upwork.com": "upwork", "xplace.com": "xplace"}
    result = {aliases.get(label, label) for label in result}
    return result


METRICS = ["discoveries", "saved_qualified_new", "full_description_recorded", "route_evidence_recorded",
           "duplicate_identities", "suppressed", "previously_reported", "history_unresolved", "prepared", "uploaded",
           "submitted_observed", "user_reported_submitted", "receipt_observed", "response_received",
           "platform_verified_historical_application", "historical_claim_only", "unverified_submission_claim", "unknown_submission"]


def build_report(found, applied, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    opportunities = found.get("opportunities", [])
    groups = identity_groups(opportunities + applied.get("records", []))
    found_object_ids = {id(row) for row in opportunities}
    by_source, identity_evidence = {}, []
    for group in groups:
        discoveries = [row for row in group if id(row) in found_object_ids]
        labels = set().union(*(source_labels(row) for row in group)) or {"unknown_source"}
        metrics = {key: False for key in METRICS}
        metrics["discoveries"] = bool(discoveries)
        metrics["duplicate_identities"] = len(discoveries) > 1
        states, times = set(), []
        for row in group:
            review = row.get("review") if isinstance(row.get("review"), dict) else {}
            metrics["saved_qualified_new"] |= row.get("status") == "qualified_new" or row.get("count_as_qualified_new") is True or review.get("decision") == "qualified_new"
            metrics["full_description_recorded"] |= row.get("full_description_read") is True or review.get("full_description_read") is True
            route = review.get("route") or row.get("route") or row.get("application_route") or {}
            if isinstance(route, dict):
                metrics["route_evidence_recorded"] |= route_evidence_recorded(route)
            history = history_decision(row, {"opportunities": discoveries}, {"records": [r for r in group if id(r) not in found_object_ids]})
            metrics["suppressed"] |= history["facts"]["suppressed"]
            metrics["previously_reported"] |= history["facts"]["previously_reported"]
            metrics["history_unresolved"] |= history["facts"]["unresolved"] or history["facts"]["possible_duplicate"]
            is_application_record = id(row) not in found_object_ids or any(key in row for key in ("submission", "submission_status", "submission_events", "submission_snapshots"))
            if is_application_record:
                states.update(state for state in application_evidence(row, now)["states"] if state != "not_recorded")
            candidates = []
            packet = row.get("application_packet")
            if isinstance(packet, dict):
                if packet.get("preparation_state") == "prepared":
                    states.add("prepared")
                candidates += packet.get("events", [])
            for event in candidates:
                if not isinstance(event, dict):
                    continue
                state = application_state(event, now)
                if state != "not_recorded":
                    states.add(state)
            for key in ("first_seen_at", "recorded_at", "last_verified_at", "reported_at", "submitted_at"):
                if timestamp(row.get(key)):
                    times.append(row[key])
        for state in states:
            metric = "unknown_submission" if state == "unknown" else state
            if metric in metrics:
                metrics[metric] = True
        ident = next((row.get("canonical_opportunity_id") or row.get("id") for row in group if row.get("id")), "unknown_identity")
        identity_evidence.append({"id": ident, "aliases": list(dict.fromkeys(str(r.get("id")) for r in group if r.get("id"))),
                                  "sources": sorted(labels), "metrics": metrics, "submission_states": sorted(states), "recorded_times": sorted(set(times))})
        for label in labels:
            bucket = by_source.setdefault(label, {key: 0 for key in METRICS})
            for key, value in metrics.items():
                bucket[key] += int(value)
    runs = [{key: run[key] for key in ("id", "checked_at", "window_start", "window_end", "requested_minimum", "qualified_count", "actual_qualified_count", "source_checks", "coverage_limited", "limitations") if key in run} for run in found.get("search_runs", [])]
    return {"schema_version": 1, "generated_at": now.isoformat(), "evidence_scope": "Saved historical canonical records only; no fresh job/form/fit checks",
            "unique_discovered_identities": sum(bool([r for r in group if id(r) in found_object_ids]) for group in groups),
            "unique_previously_reported_identities": sum(item["metrics"]["previously_reported"] for item in identity_evidence),
            "by_source": dict(sorted(by_source.items())), "identities": identity_evidence, "recorded_runs": runs,
            "limits": ["Sources may share an identity; per-source columns cannot be summed as global totals.",
                       "Saved qualified/description/route decisions are attributed records, not new verification.",
                       "Unknown or absent evidence is not zero real-world activity; rates and recruiter interest are not inferred.",
                       "Prepared, uploaded, observed submission, user-reported submission, receipt and response are independent counts."]}


def markdown(report):
    rows = ["# Workhunt source outcomes", "", report["evidence_scope"] + ".", "",
            f"Generated: {report['generated_at']}. Distinct recorded discovery identities: {report['unique_discovered_identities']}. Ever reported: {report['unique_previously_reported_identities']} distinct identities.", "",
            "| Source | Discoveries | Saved qualified new | Full description | Route evidence | Duplicates | Suppressed | Ever reported | Prepared | Observed submitted | User reported | Receipt | Response |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    keys = ["discoveries", "saved_qualified_new", "full_description_recorded", "route_evidence_recorded", "duplicate_identities", "suppressed", "previously_reported", "prepared", "submitted_observed", "user_reported_submitted", "receipt_observed", "response_received"]
    for source, counts in report["by_source"].items():
        rows.append("| " + source.replace("|", "\\|") + " | " + " | ".join(str(counts[k]) for k in keys) + " |")
    rows += ["", "Upload, historical platform observation, unresolved history and unknown submission counts are retained separately in the companion JSON. Recorded timestamps and original run outcomes are retained there; no unsupported conversion or response-rate estimate is calculated.", ""]
    rows += ["- " + limit for limit in report["limits"]]
    return "\n".join(rows) + "\n"


def write_report(workdir, output, json_output=None):
    workdir = private_root(workdir)
    paths = [workdir / "data/jobs.json", workdir / "data/applied_jobs.json"]
    raw = [p.read_bytes() for p in paths]
    profile = load(workdir / "profile.json", {})
    timezone = profile.get("timezone")
    if not timezone:
        raise ValueError("Outcome reporting requires an explicitly configured time zone")
    report = build_report(*(json.loads(value.decode("utf-8-sig")) for value in raw), now=dt.datetime.now(ZoneInfo(timezone)))
    report["input_sha256"] = {p.name: hashlib.sha256(value).hexdigest() for p, value in zip(paths, raw)}
    outputs = [safe_output(workdir, output), safe_output(workdir, json_output or Path(output).with_suffix(".json"))]
    if outputs[0] == outputs[1]:
        raise ValueError("Markdown and JSON outputs must be distinct")
    for path, content in zip(outputs, [markdown(report), json.dumps(report, ensure_ascii=False, indent=2) + "\n"]):
        if path.resolve() in [p.resolve() for p in paths]:
            raise ValueError("Outcome report must not replace canonical input records")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workdir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    report = write_report(args.workdir, args.output, args.json_output)
    print(json.dumps({"output": str(args.output), "sources": len(report["by_source"]), "unique_discovered_identities": report["unique_discovered_identities"]}))
