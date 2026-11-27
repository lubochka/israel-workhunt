"""Separate identified work from admission; a response mode is not the work itself."""
import copy
import re
from records import norm, url_identity

SOURCE_ACCESS_KINDS = {"source_access", "network_admission", "generic_screening", "platform_invitation", "profile", "service"}
SOURCE_ACCESS_MODES = {"network_admission", "generic_agency_screening", "platform_invitation"}


def supported_text(value):
    return isinstance(value, str) and bool(value.strip())


def first_text(record, *keys):
    return next((record[key] for key in keys if supported_text(record.get(key))), None)


def project_scope_evidence(record, review=None):
    review = review if isinstance(review, dict) else {}
    scope = review.get("project_scope", record.get("project_scope"))
    scope = scope if isinstance(scope, dict) else {}
    urls = {url_identity(record.get(key)) for key in ("url", "source_url", "listing_url")} - {"", None}
    deliverables = scope.get("deliverables")
    return scope if (scope.get("paid_client_work") is True and supported_text(scope.get("evidence"))
                     and url_identity(scope.get("source_url")) in urls
                     and isinstance(deliverables, list) and deliverables and all(supported_text(item) for item in deliverables)) else {}


def client_project_type(record, review=None):
    return record.get("type") in {"project", "paid_project"} or (
        record.get("type") == "contract" and project_scope_evidence(record, review).get("engagement_type") == "client_project")


def project_discovery_candidate(record, review=None):
    review = review if isinstance(review, dict) else {}
    return bool(client_project_type(record, review)
                and record.get("record_kind") not in SOURCE_ACCESS_KINDS
                and record.get("response_mode") not in SOURCE_ACCESS_MODES
                and first_text(record, "id", "opportunity_id")
                and url_identity(first_text(record, "url", "listing_url", "source_url"))
                and (first_text(record, "title", "description", "description_evidence") or first_text(review, "description_evidence")))


def identified_project(record, review=None):
    review = review if isinstance(review, dict) else {}
    return bool(project_discovery_candidate(record, review)
                and first_text(record, "company", "employer_or_client", "source_job_id", "project_id")
                and (first_text(record, "description", "description_evidence") or first_text(review, "description_evidence")))


def route_owner_matches(record, route, review=None):
    owner = norm(first_text(record, "company", "employer_or_client"))
    if owner:
        return supported_text(route.get("employer")) and norm(route["employer"]) == owner
    ids = {norm(record[key]) for key in ("source_job_id", "project_id") if supported_text(record.get(key))}
    return bool(identified_project(record, review) and supported_text(route.get("project_id")) and norm(route["project_id"]) in ids)


def project_alternatives(policy):
    """Interpret explicit private policy; never rewrite a saved snapshot or infer adoption."""
    if not isinstance(policy, dict):
        return []
    if "configured" in policy or "alternatives" in policy:
        if policy.get("configured") is not True or not isinstance(policy.get("alternatives"), list):
            return []
        alternatives = policy["alternatives"]
    elif policy.get("angular_frontend_without_dotnet") is True:
        # Compatibility only for an explicitly recorded legacy choice, never defaults.
        return [{"id": "legacy_frontend", "required_capabilities": ["angular"],
                 "discovery_patterns": {"angular": r"\bangular(?:js|\d+(?:\.\d+)*)?\b"}, "legacy_format": True}]
    else:
        return []
    result, ids = [], set()
    for entry in alternatives:
        if not isinstance(entry, dict) or not supported_text(entry.get("id")) or entry["id"] in ids:
            return []
        required, patterns = entry.get("required_capabilities"), entry.get("discovery_patterns")
        if (not isinstance(required, list) or not required or any(not supported_text(key) for key in required)
                or len(set(required)) != len(required) or not isinstance(patterns, dict) or set(patterns) != set(required)):
            return []
        try:
            for pattern in patterns.values():
                if not supported_text(pattern) or any(re.search(pattern, value, re.I) for value in ("", "unrelated arbitrary text", "12345")):
                    return []
        except (re.error, TypeError):
            return []
        ids.add(entry["id"])
        result.append({"id": entry["id"], "required_capabilities": copy.deepcopy(required), "discovery_patterns": copy.deepcopy(patterns)})
    return result


def scope_capabilities(scope, alternative):
    if "capabilities" in scope:
        return scope["capabilities"] if isinstance(scope["capabilities"], dict) else {}
    return {"angular": True} if alternative.get("legacy_format") and scope.get("angular_frontend") is True else {}


def source_access_record(record, review=None):
    return (record.get("record_kind") in SOURCE_ACCESS_KINDS
            or record.get("response_mode") in SOURCE_ACCESS_MODES
            or record.get("response_mode") == "client_invitation" and not identified_project(record, review))
