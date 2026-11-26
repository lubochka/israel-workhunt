"""Offline source selection and public-page evidence semantics; never fetches or searches."""
import copy
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlsplit
from profile_config import shared_root, private_path
from records import norm, url_identity
from opportunity_types import identified_project, source_access_record


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
    if source_access_record(record, record.get("review")):
        return False
    if record.get("response_mode") == "client_invitation":
        return identified_project(record, record.get("review"))
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


ROUTE_METHODS = {"public_page", "isolated_browser", "public_search"}


def route_attempt_key(url, method="public_page"):
    identity = url_identity(url) if supported_text(url) else None
    if not identity or not isinstance(method, str) or method not in ROUTE_METHODS:
        raise ValueError("A route attempt requires a public URL and supported explicit method")
    return identity, method


TARGET_FIELDS = ("target_id", "source_id", "source", "employer_id", "employer")


def _label_key(value):
    if not isinstance(value, str) or not value.strip():
        return None
    return url_identity(value) if "://" in value else value.strip().casefold()


def _labels(source):
    return {_label_key(value) for value in [source.get("id"), source.get("name"), source.get("website"), *source.get("aliases", [])]} - {None}


def _route_urls(source):
    # Original catalog channels may have only a website, not manual_routes.
    # Its exact URL is a navigation anchor, never permission for every host path.
    return {url_identity(source.get("website")), *(url_identity(route.get("url")) for route in source.get("manual_routes", []))} - {None, ""}


def observation_binding(source, observation, targets=None, require_evidence=True):
    """Bind supplied evidence, never infer ownership from a hostname or an alias URL prefix."""
    rows = list(targets) if targets is not None else [source]
    own = source.get("id")
    own_indexes = {i for i, row in enumerate(rows) if row is source or (own and row.get("id") == own)}
    if not own_indexes:
        rows.append(source)
        own_indexes = {len(rows) - 1}
    result = {"bound": False, "target_id": own, "reason": "No observation for this target"}

    def owners(url):
        return {i for i, row in enumerate(rows) if url in _route_urls(row)} if url else set()

    def unique_own(matches):
        return len(matches) == 1 and bool(matches & own_indexes)

    explicit = False
    for key in TARGET_FIELDS:
        if key not in observation:
            continue
        explicit = True
        value = _label_key(observation[key])
        matches = {i for i, row in enumerate(rows) if value and value in _labels(row)}
        if not unique_own(matches):
            return {**result, "reason": "Conflicting, unknown or ambiguous explicit target identity", "field": key}
    url = url_identity(observation.get("source_url"))
    if not url:
        return result
    evidence = observation.get("evidence")
    if require_evidence and (not isinstance(evidence, str) or not evidence.strip()):
        return {**result, "reason": "Target evidence must be nonblank text"}
    matches = owners(url)
    navigation = observation.get("navigation")

    def linked(start, end):
        return (isinstance(navigation, dict)
                and url_identity(navigation.get("from_url")) == start
                and url_identity(navigation.get("to_url")) == end
                and isinstance(navigation.get("evidence"), str) and bool(navigation["evidence"].strip()))

    if matches and not unique_own(matches):
        return {**result, "reason": "Observed route belongs to another or ambiguous target"}
    if not matches:
        origin = url_identity(navigation.get("from_url")) if isinstance(navigation, dict) else None
        if not (explicit and unique_own(owners(origin)) and linked(origin, url)):
            return {**result, "reason": "No exact configured route or evidenced target navigation"}
    resolved = url_identity(observation.get("resolved_url"))
    if observation.get("resolved_url") and (not resolved or (resolved != url and not unique_own(owners(resolved)) and not (not owners(resolved) and linked(url, resolved)))):
        return {**result, "reason": "Redirect is unrelated, ambiguous or lacks paired navigation evidence"}
    return {**result, "bound": True, "reason": "Explicit target and exact route/navigation" if explicit else "Legacy unique exact configured route",
            "source_url": observation["source_url"]}


def target_coverage(source, observation, targets=None):
    binding = observation_binding(source, observation, targets)
    if binding["bound"]:
        state = coverage_observation(observation)
    else:
        state = coverage_observation({"transport_status": "not_attempted"})
        state["ignored_observation"] = copy.deepcopy(observation)
    return {**state, "target_id": source.get("id"), "binding": binding}


def select_observation(source, observations, targets):
    """One observation per target/scope; never silently aggregate categories or pick a winner."""
    candidates = []
    for observation in observations:
        explicit = any(_label_key(observation.get(key)) in _labels(source) for key in TARGET_FIELDS)
        exact = url_identity(observation.get("source_url")) in _route_urls(source)
        if explicit or exact or observation_binding(source, observation, targets)["bound"]:
            candidates.append(observation)
    if len(candidates) > 1:
        raise ValueError("Multiple observations for target " + str(source.get("id")) + "; supply one explicit bounded scope per target")
    return candidates[0] if candidates else {}


def fallback_plan(source, observation, attempted_urls=(), profile=None, *, attempted_routes=(), targets=None):
    """Plan remaining pairs; the fourth positional argument remains the private profile."""
    state = target_coverage(source, observation, targets)
    base = {"target_id": source.get("id"), "binding": state["binding"], "executes_network": False}
    if not state["binding"]["bound"]:
        base["ignored_observation"] = state["ignored_observation"]
    if state["status"] in {"checked", "checked_empty"}:
        return {**base, "status": state["status"], "next_routes": [], "executes_network": False, "reason": "Selected route completed its evidenced scope; do not retry it as an access failure"}
    count = observation.get("observed_count")
    if (state["status"] == "partial" and observation.get("transport_status") == "success"
            and observation.get("content_kind") == "opportunity_list"
            and type(count) is int and count > 0
            and supported_text(observation.get("evidence")) and supported_text(observation.get("source_url"))):
        return {**base, "status": "partial", "next_routes": [], "next_action": "continue_selected_route_coverage",
                "reason": "Continue remaining pages on the working selected route", "executes_network": False}
    # Bounded: each documented public alternative once; no auth bypass or brute force.
    tried, ignored_attempts = set(), []
    attempts = [{"url": url, "method": "public_page"} for url in attempted_urls]
    attempts += [*observation.get("attempted_routes", []), *attempted_routes]
    if state["binding"]["bound"]:
        if observation.get("transport_status", "not_attempted") != "not_attempted":
            attempts.append({**observation, "url": observation["source_url"], "method": observation.get("method", "public_page")})
        for attempt in attempts:
            if not isinstance(attempt, dict):
                ignored_attempts.append({"attempt": copy.deepcopy(attempt), "binding": {"bound": False, "reason": "Attempt is not a target-bound object"}})
                continue
            scoped = {**attempt, "source_url": attempt.get("url")}
            binding = observation_binding(source, scoped, targets, require_evidence=False)
            if not binding["bound"]:
                ignored_attempts.append({"attempt": copy.deepcopy(attempt), "binding": binding})
                continue
            # Foreign malformed attempts stay diagnostic; own attempts need an explicit method.
            key = route_attempt_key(attempt.get("url"), attempt.get("method"))
            tried.add(key)
            if supported_text(attempt.get("resolved_url")):
                tried.add(route_attempt_key(attempt["resolved_url"], attempt["method"]))
    else:
        ignored_attempts = [{"attempt": copy.deepcopy(attempt), "binding": {"bound": False, "reason": "Parent observation is not bound to this target"}} for attempt in attempts]
    routes, unresolved, planned = [], [], set()
    for route in source.get("manual_routes", []):
        if not route.get("enabled", True):
            continue
        applicability = route_applicability(route, profile)
        if applicability["status"] != "applicable":
            unresolved.append({"url": route.get("url"), "applicability_check": applicability})
            continue
        method = route.get("method", "public_page")
        key = route_attempt_key(route.get("url"), method)
        if key not in tried and key not in planned:
            planned.add(key)
            routes.append({**copy.deepcopy(route), "method": method, "applicability_check": applicability})
    return {**base, "status": state["status"], "ignored_attempts": ignored_attempts, "next_routes": routes[:3], "unrecommended_scoped_routes": unresolved, "max_attempts_per_route": 1,
            "attempt_identity": "functional URL plus method", "legacy_attempted_urls_method": "public_page", "exhausted": not routes,
            "reason": "Use documented public alternatives; preserve original failure and redirects and stop after available pairs",
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
        if not isinstance(employer_identity, dict) or not all(supported_text(employer_identity.get(k)) for k in ("id", "url", "employer", "source_job_id", "identity_evidence")):
            raise ValueError("Employer alias requires exact requisition and linkage evidence")
        alias = copy.deepcopy(employer_identity)
        if not url_identity(alias["url"]):
            raise ValueError("Employer alias requires a public listing URL")
        if any(norm(alias.get(key)) and norm(alias[key]) != norm(alias["employer"]) for key in ("company", "employer_or_client")):
            raise ValueError("Employer alias contains conflicting employer fields")
        if alias.get("source_url") and url_identity(alias["source_url"]) != url_identity(alias["url"]):
            raise ValueError("Employer alias contains conflicting listing URLs")
        if not norm(alias.get("company")):
            alias["company"] = alias["employer"]
        if "employer_or_client" in alias and not norm(alias["employer_or_client"]):
            alias["employer_or_client"] = alias["employer"]
        row["source_aliases"] = [alias]
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
        supplied = json.loads(private_path(args.workspace, args.observation).read_text(encoding="utf-8"))
        observations = supplied.get("observations", [supplied]) if isinstance(supplied, dict) else None
        if not isinstance(observations, list) or not all(isinstance(item, dict) for item in observations):
            raise ValueError("Supply one observation object or {observations: [objects]}")
        targets = [*catalog["sources"].values(), *catalog["lifecycle_references"].values(), *catalog["employer_fallbacks"]]
        result["coverage"], result["fallbacks"] = {}, {}
        for row in [*selected, *employer_routes]:
            observation = select_observation(row, observations, targets)
            state = target_coverage(row, observation, targets)
            state["other_observations"] = [copy.deepcopy(item) for item in observations if item is not observation]
            result["coverage"][row["id"]] = state
            result["fallbacks"][row["id"]] = fallback_plan(row, observation, observation.get("attempted_urls", []), profile, targets=targets)
    print(json.dumps(result, ensure_ascii=False, indent=2))
