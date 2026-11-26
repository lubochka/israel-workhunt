"""Offline source selection and public-page evidence semantics; never fetches or searches."""
import copy
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlsplit
from profile_config import shared_root, private_path


def supported_text(value):
    return isinstance(value, str) and bool(value.strip())


def source_key(value):
    text = str(value).strip().casefold().rstrip("/")
    if "://" in text:
        parts = urlsplit(text)
        text = parts.netloc.removeprefix("www.") + parts.path.rstrip("/")
    return text


def load_catalog(workspace, shared=None):
    """Read public catalogs from the resolved release, independently of private records."""
    root = Path(shared).resolve() if shared is not None else shared_root(workspace)
    base = json.loads((root / "sources/opportunity-sources.json").read_text(encoding="utf-8"))
    extra = json.loads((root / "sources/manual-discovery.json").read_text(encoding="utf-8"))
    rows = {row["id"]: copy.deepcopy(row) for row in base["sources"]}
    for row in extra["sources"]:
        if row["id"] in rows:
            raise ValueError("Supplement duplicates an existing source; use source_overrides")
        rows[row["id"]] = copy.deepcopy(row)
    for identifier, override in extra.get("source_overrides", {}).items():
        if identifier not in rows:
            raise ValueError("Unknown override source: " + identifier)
        if {"id", "evidence", "follow_up_evidence"} & override.keys():
            raise ValueError("Overrides must preserve source identity and historical evidence")
        rows[identifier].update(copy.deepcopy(override))
    references = {row["id"]: copy.deepcopy(row) for row in extra.get("lifecycle_references", [])}
    if rows.keys() & references.keys():
        raise ValueError("Lifecycle reference duplicates a selected source")
    index = {}
    for row in [*rows.values(), *references.values()]:
        for label in [row["id"], row["name"], row.get("website", ""), *row.get("aliases", [])]:
            if not label:
                continue
            key = source_key(label)
            if key in index and index[key] != row["id"]:
                raise ValueError("Ambiguous source alias: " + key)
            index[key] = row["id"]
    return {"sources": rows, "lifecycle_references": references, "alias_index": index, "employer_fallbacks": extra.get("employer_fallbacks", []),
            "directory_provenance": extra["directory_provenance"]}


def resolve_source(catalog, value):
    identifier = catalog["alias_index"].get(source_key(value))
    if identifier is None:
        raise ValueError("Unknown source; do not guess a successor: " + str(value))
    return copy.deepcopy(catalog["sources"].get(identifier) or catalog["lifecycle_references"][identifier])


def route_applicability(route, profile=None):
    """Scope is source relevance from explicit preferences, never legal eligibility."""
    scope = route.get("applicability") or {}
    if not scope:
        return {"status": "applicable", "reason": "No candidate-specific scope recorded for this public reference", "qualification_verified": False}
    profile = profile or {}
    if profile.get("configured") is not True:
        return {"status": "unknown", "reason": "Scoped route requires an explicitly configured profile", "qualification_verified": False}
    fields = {"eligible_countries_any": profile.get("eligible_countries"),
              "required_stack_any": (profile.get("search_brief") or {}).get("required_stack")}
    missing, unmatched = [], []
    for key, required in scope.items():
        selected = fields.get(key)
        if (key not in fields or not isinstance(required, list) or not required
                or any(not supported_text(v) for v in required)
                or not isinstance(selected, list) or not selected or any(not supported_text(v) for v in selected)):
            missing.append(key)
        elif not {v.strip().casefold() for v in required} & {v.strip().casefold() for v in selected}:
            unmatched.append(key)
    status = "inapplicable" if unmatched else "unknown" if missing else "applicable"
    return {"status": status, "unmatched_preferences": unmatched, "missing_preferences": missing,
            "reason": "Compared retained route scope with explicit current search preferences; no inference from CV or source history",
            "qualification_verified": False}


def select_sources(catalog, values, profile=None):
    # Aliases collapse source planning only, never employer/requisition identities.
    selected = {}
    for value in values:
        row = resolve_source(catalog, value)
        row["manual_routes"] = [{**route, "applicability_check": route_applicability(route, profile)} for route in row.get("manual_routes", [])]
        row["recommended_routes"] = [copy.deepcopy(route) for route in row["manual_routes"] if route["applicability_check"]["status"] == "applicable" and route.get("enabled", True)]
        selected.setdefault(row["id"], row)
    return list(selected.values())


def opportunity_candidate(record):
    """Admission/profile/service pages cannot become jobs by supplying a source ID."""
    return (record.get("record_kind") == "opportunity"
            and record.get("response_mode") in {"vacancy_application", "project_proposal", "agency_vacancy", "agency_screening"}
            and supported_text(record.get("opportunity_id")) and supported_text(record.get("listing_url"))
            and supported_text(record.get("employer_or_client")) and supported_text(record.get("description_evidence")))


def coverage_observation(observation):
    """Classify evidence for one bounded query/page scope, never the whole Internet."""
    result = copy.deepcopy(observation)
    count = observation.get("observed_count")
    valid_count = type(count) is int and count >= 0
    transport = observation.get("transport_status", "not_attempted")
    if transport == "not_attempted":
        status = "not_attempted"
    elif transport in {"blocked", "failed", "timeout", "rate_limited"}:
        status = "partial" if valid_count and count > 0 else "blocked"
    elif transport != "success":
        raise ValueError("Unknown transport_status")
    elif observation.get("content_kind") not in {"opportunity_list", "opportunity_detail"}:
        status = "partial"  # HTML line count, JS shell, generic home/login are not lists.
    elif not supported_text(observation.get("evidence")) or not supported_text(observation.get("source_url")) or not valid_count:
        status = "partial"
    elif count > 0:
        status = "checked" if observation.get("scope_complete") is True else "partial"
    elif observation.get("scope_complete") is True and supported_text(observation.get("explicit_empty_evidence")):
        status = "checked_empty"
    else:
        status = "partial"
    result.update(status=status, coverage_complete=status in {"checked", "checked_empty"},
                  vacancy_or_form_verified=False, collector_health_updated=False)
    return result


def fallback_plan(source, observation, attempted_urls=(), profile=None):
    state = coverage_observation(observation)
    if state["status"] == "checked_empty":
        return {"status": "checked_empty", "next_routes": [], "executes_network": False, "reason": "Explicit empty result in the recorded completed scope; do not retry it as an access failure"}
    # Bounded: each documented public alternative once; no auth bypass or brute force.
    tried = {source_key(url) for url in attempted_urls}
    routes, unresolved = [], []
    for route in source.get("manual_routes", []):
        applicability = route_applicability(route, profile)
        if applicability["status"] != "applicable":
            unresolved.append({"url": route.get("url"), "applicability_check": applicability})
            continue
        key = source_key(route.get("url", ""))
        if key and key not in tried and route.get("enabled", True):
            tried.add(key)
            routes.append({**copy.deepcopy(route), "applicability_check": applicability})
    return {"status": state["status"], "next_routes": routes[:3], "unrecommended_scoped_routes": unresolved, "max_attempts_per_route": 1,
            "reason": "Use documented public alternatives; preserve original failure and stop after available routes",
            "executes_network": False}


def hn_candidate(item, thread_id=None, employer_identity=None):
    """Normalize already retrieved public HN item evidence, not a collector/API call."""
    if not isinstance(item, dict) or item.get("deleted") or item.get("dead"):
        return None
    kind = item.get("type")
    if kind not in {"comment", "job"} or type(item.get("id")) is not int or type(item.get("time")) is not int:
        return None
    if kind == "comment" and (type(thread_id) is not int or item.get("parent") != thread_id):
        return None
    url = "https://news.ycombinator.com/item?id=" + str(item["id"])
    try:
        at = dt.datetime.fromtimestamp(item["time"], dt.timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return None
    row = {"id": "hn:" + str(item["id"]), "source": "hn", "source_job_id": str(item["id"]),
           "url": url, "source_url": url, "hn_item_type": kind, "thread_id": thread_id if kind == "comment" else None,
           "parent_item_id": item.get("parent"), "title": item.get("title", ""), "description": item.get("text", ""),
           "description_complete": False, "discovery_only": True,
           "publication_events": [{"kind": "original", "at": at, "source_url": url,
                                   "evidence": "HN item.time for this exact " + kind,
                                   "scope": "hiring_comment" if kind == "comment" else "job_story"}],
           "employer_listing_url": item.get("url"), "refresh_evidence": None}
    if employer_identity:
        # Only explicit observed same-requisition linkage can become an identity alias.
        if not all(supported_text(employer_identity.get(k)) for k in ("id", "url", "employer", "source_job_id", "identity_evidence")):
            raise ValueError("Employer alias requires exact requisition and linkage evidence")
        row["source_aliases"] = [copy.deepcopy(employer_identity)]
    return row


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--shared-root", type=Path, help="Explicit public release root; private records stay in workspace/.workhunt")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--employer", action="append", default=[], help="Named documented employer fallback; no ATS tenant mutation")
    parser.add_argument("--observation", type=Path, help="Optional local coverage observation JSON; no provider requests")
    args = parser.parse_args()
    catalog = load_catalog(args.workspace, args.shared_root)
    from records import load
    profile = load(private_path(args.workspace, "profile.json"), {})
    selected = select_sources(catalog, args.source or ([] if args.employer else list(catalog["sources"])), profile)
    result = {"sources": selected, "count": len(selected), "executes_network": False}
    employer_routes = [row for row in catalog["employer_fallbacks"] if any(source_key(value) in {source_key(row["id"]), source_key(row["name"])} for value in args.employer)]
    if len(employer_routes) != len(set(map(source_key, args.employer))):
        raise ValueError("Unknown or duplicate employer fallback selection")
    result["employer_fallbacks"] = employer_routes
    if args.observation:
        observation = json.loads(private_path(args.workspace, args.observation).read_text(encoding="utf-8"))
        result["coverage"] = coverage_observation(observation)
        result["fallbacks"] = {row["id"]: fallback_plan(row, observation, observation.get("attempted_urls", []), profile) for row in [*selected, *employer_routes]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
