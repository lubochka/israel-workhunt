"""Shared route status vocabulary; identity, recency and eligibility stay separate."""
import copy


def normalize_route(value):
    route = copy.deepcopy(value) if isinstance(value, dict) else {}
    recorded_status = route.get("status") or route.get("decision")
    route["status"] = {"exact_application_form_verified": "form_observed", "qualified_login": "login_required"}.get(recorded_status, recorded_status)
    if recorded_status == "qualified_login":
        route.setdefault("exact_vacancy_accepting_applications", True)
    route.setdefault("source_url", route.get("exact_job_url") or route.get("url"))
    route.setdefault("checked_at", route.get("verified_at"))
    route.setdefault("job_identifier", route.get("job_id_in_page"))
    return route


def observed_form(value, allow_proposal=False):
    status = normalize_route(value).get("status")
    return status == "form_observed" or allow_proposal and status == "proposal_observed"


def route_evidence_recorded(value, allow_proposal=True):
    """Saved evidence only; freshness and exact linkage require their own checks."""
    route = normalize_route(value)
    return bool(route.get("evidence")) and (observed_form(route, allow_proposal)
        or route.get("status") == "login_required" and route.get("exact_vacancy_accepting_applications") is True)
