"""Read-only source outcome report from saved canonical evidence; no fresh job verification."""
import argparse
import datetime as dt
import hashlib
import json
import math
import copy
import re
from profile_config import private_root, safe_output
from pathlib import Path
import urllib.parse as up
from zoneinfo import ZoneInfo
from records import application_evidence, application_state, history_decision, identity_groups, load, timestamp
from qualification import route_evidence_recorded
from discovery_routes import load_catalog, source_key


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


def canonical_source(value, catalog=None):
    return (catalog or {}).get("alias_index", {}).get(source_key(value), str(value).strip().casefold())


def operational_evidence(found, groups, now, catalog=None):
    """Optional supplied evidence, not estimates from volume, elapsed run bounds or bids."""
    candidates, malformed = [], []
    def collect(value, identity, location):
        if not isinstance(value, list):
            malformed.append({"location": location, "reason": "Event collection must be an array", "recorded_value": copy.deepcopy(value)})
            return
        for index, event in enumerate(value):
            candidates.append((event, identity, location + "/" + str(index)))
    for group_number, group in enumerate(groups):
        for row_number, row in enumerate(group):
            if "outcome_events" in row:
                collect(row["outcome_events"], group_number, f"identity_groups/{group_number}/{row_number}/outcome_events")
    for run_number, run in enumerate(found.get("search_runs", [])):
        if "source_activity" in run:
            collect(run["source_activity"], None, f"search_runs/{run_number}/source_activity")
    events, conflicts = {}, set()
    for event, identity, location in candidates:
        if not isinstance(event, dict) or not isinstance(event.get("event_id"), str) or not event["event_id"].strip():
            malformed.append({"location": location, "reason": "Event object with nonblank string event_id required", "recorded_value": copy.deepcopy(event)})
            continue
        identifier = event["event_id"]
        entry = (event, identity)
        if identifier in events and events[identifier] != entry:
            # Identical cross-post copies resolve to one identity group; different
            # payloads/identity claims with a reused ID are unresolved, not additive.
            conflicts.add(identifier)
        else:
            events[identifier] = entry
    by_source, valid, rejected = {}, [], []
    for identifier, (event, identity) in events.items():
        at = timestamp(event.get("at"))
        kind = event.get("kind") if isinstance(event.get("kind"), str) else None
        source = event.get("source")
        ok = identifier not in conflicts and isinstance(source, str) and bool(source.strip()) and isinstance(event.get("evidence"), str) and bool(event["evidence"].strip()) and at is not None and at.timestamp() <= now.timestamp()
        source = canonical_source(source, catalog)
        if identity is not None:
            linked_sources = {canonical_source(label, catalog) for row in groups[identity] for label in source_labels(row)}
            ok = ok and (source in linked_sources or isinstance(event.get("source_attribution_evidence"), str) and bool(event["source_attribution_evidence"].strip()))
        amount = event.get("seconds") if kind == "research_time" else event.get("amount")
        if kind in {"research_time", "proposal_spend"}:
            ok = ok and type(amount) in {int, float} and math.isfinite(amount) and amount >= 0
            if kind == "proposal_spend":
                ok = ok and isinstance(event.get("currency"), str) and re.fullmatch(r"[A-Za-z]{3}", event["currency"]) is not None
        elif kind in {"reply_observed", "interview_observed", "paid_engagement_observed"}:
            ok = ok and identity is not None
        else:
            ok = False
        if not ok:
            rejected.append(identifier)
            continue
        bucket = by_source.setdefault(source, {"research_seconds": None, "research_event_count": 0,
            "proposal_spend_by_currency": {}, "spend_event_count": 0, "reply_identities": set(),
            "interview_identities": set(), "paid_engagement_identities": set(), "evidence_event_ids": []})
        bucket["evidence_event_ids"].append(identifier)
        if kind == "research_time":
            bucket["research_seconds"] = (bucket["research_seconds"] or 0) + amount
            bucket["research_event_count"] += 1
        elif kind == "proposal_spend":
            currency = event["currency"].upper()
            bucket["proposal_spend_by_currency"][currency] = bucket["proposal_spend_by_currency"].get(currency, 0) + amount
            bucket["spend_event_count"] += 1
        else:
            key = {"reply_observed": "reply_identities", "interview_observed": "interview_identities", "paid_engagement_observed": "paid_engagement_identities"}[kind]
            bucket[key].add(identity)
        valid.append(event)
    for bucket in by_source.values():
        for key in ("reply_identities", "interview_identities", "paid_engagement_identities"):
            bucket[key] = len(bucket[key]) if bucket[key] else None
    return {"by_source": by_source, "supported_event_count": len(valid), "unresolved_event_ids": sorted(rejected),
            "malformed_events": malformed, "unresolved_events": [{"event_id": identifier, "recorded_event": copy.deepcopy(events[identifier][0]), "conflicting_id": identifier in conflicts} for identifier in sorted(rejected)],
            "events": valid, "limits": "Absent effort/cost/outcome evidence is unknown. Recorded spending is not an offer/rate. No conversion, income or causal attribution inferred."}


def build_report(found, applied, now=None, source_catalog=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    opportunities = found.get("opportunities", [])
    groups = identity_groups(opportunities + applied.get("records", []))
    found_object_ids = {id(row) for row in opportunities}
    by_source, identity_evidence = {}, []
    for group in groups:
        discoveries = [row for row in group if id(row) in found_object_ids]
        labels = {canonical_source(label, source_catalog) for row in group for label in source_labels(row)} or {"unknown_source"}
        metrics = {key: False for key in METRICS}
        metrics["discoveries"] = bool(discoveries)
        metrics["duplicate_identities"] = len(discoveries) > 1
        states, times, rejections = set(), [], set()
        for row in group:
            review = row.get("review") if isinstance(row.get("review"), dict) else {}
            if (review.get("decision") or row.get("status")) in {"excluded", "needs_clarification", "not_qualified"}:
                for key in ("reason", "reasons", "hard_exclusions", "exclusion_reasons", "gaps"):
                    for container in (row, review):
                        value = container.get(key)
                        rejections.update([value] if isinstance(value, str) else [v for v in value if isinstance(v, str)] if isinstance(value, list) else [])
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
                                  "sources": sorted(labels), "metrics": metrics, "submission_states": sorted(states), "recorded_times": sorted(set(times)), "saved_rejection_reasons": sorted(rejections)})
        for label in labels:
            bucket = by_source.setdefault(label, {key: 0 for key in METRICS})
            for key, value in metrics.items():
                bucket[key] += int(value)
    runs = [{key: run[key] for key in ("id", "checked_at", "window_start", "window_end", "requested_minimum", "qualified_count", "actual_qualified_count", "source_checks", "coverage_limited", "limitations") if key in run} for run in found.get("search_runs", [])]
    operational = operational_evidence(found, groups, now, source_catalog)
    for label, counts in by_source.items():
        bucket = operational["by_source"].setdefault(label, {"research_seconds": None, "research_event_count": 0, "proposal_spend_by_currency": {}, "spend_event_count": 0, "reply_identities": None, "interview_identities": None, "paid_engagement_identities": None, "evidence_event_ids": []})
        bucket["discovery_denominator"] = counts["discoveries"]
        bucket["saved_qualified_numerator"] = counts["saved_qualified_new"]
        bucket["saved_duplicate_share"] = counts["duplicate_identities"] / counts["discoveries"] if counts["discoveries"] else None
        bucket["saved_rejections_by_reason"] = {}
        for identity in identity_evidence:
            if label in identity["sources"]:
                for reason in identity["saved_rejection_reasons"]:
                    bucket["saved_rejections_by_reason"][reason] = bucket["saved_rejections_by_reason"].get(reason, 0) + 1
    return {"schema_version": 1, "generated_at": now.isoformat(), "evidence_scope": "Saved historical canonical records only; no fresh job/form/fit checks",
            "unique_discovered_identities": sum(bool([r for r in group if id(r) in found_object_ids]) for group in groups),
            "unique_previously_reported_identities": sum(item["metrics"]["previously_reported"] for item in identity_evidence),
            "by_source": dict(sorted(by_source.items())), "identities": identity_evidence, "recorded_runs": runs, "operational_evidence": operational,
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
    rows += ["| Source | Recorded research seconds | Actual proposal spend | Observed replies | Interviews | Paid engagements |", "| --- | ---: | --- | ---: | ---: | ---: |"]
    for source, value in sorted(report.get("operational_evidence", {}).get("by_source", {}).items()):
        show = lambda v: "unknown" if v is None else str(v)
        spending = ", ".join(f"{amount} {currency}" for currency, amount in sorted(value["proposal_spend_by_currency"].items())) or "unknown"
        rows.append("| " + source.replace("|", "\\|") + " | " + " | ".join([show(value["research_seconds"]), spending, show(value["reply_identities"]), show(value["interview_identities"]), show(value["paid_engagement_identities"])]) + " |")
    rows += ["", "Only supplied dated evidence supports effort, expenditure or response outcomes. Unknown does not mean zero. Saved rejection reasons, duplicate denominators and event provenance are in JSON.", ""]
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
    report = build_report(*(json.loads(value.decode("utf-8-sig")) for value in raw), now=dt.datetime.now(ZoneInfo(timezone)), source_catalog=load_catalog(workdir))
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
