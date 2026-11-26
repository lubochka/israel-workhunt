"""Exact-opportunity evidence for configured country/work-path preferences."""
import copy
from records import norm, timestamp, url_identity

DEFAULT_POLICY = {
    "base_country": None, "work_path": None,
    "exclude_required_foreign_conditions": [], "unknown_eligibility": None,
    "candidate_legal_status": "unknown", "provenance": {},
}
CONDITION_KINDS = {"work_visa", "work_permit", "right_to_work", "residency", "relocation", "office_only", "travel"}


def policy_for(profile=None):
    configured = (profile or {}).get("work_location_policy")
    return {**copy.deepcopy(DEFAULT_POLICY), **copy.deepcopy(configured if isinstance(configured, dict) else {})}


def policy_gaps(policy):
    gaps = []
    country = policy.get("base_country")
    if not isinstance(country, str) or len(country) != 2 or not country.isascii() or not country.isalpha():
        gaps.append("Work-location base_country must be an explicit two-letter country code")
    if not text(policy.get("work_path")) or norm(policy["work_path"]) in {"unknown", "unspecified"}:
        gaps.append("Work-location work_path must be explicitly selected")
    conditions = policy.get("exclude_required_foreign_conditions")
    if not isinstance(conditions, list) or any(not isinstance(k, str) or k not in CONDITION_KINDS for k in conditions):
        gaps.append("Work-location exclusions must be an explicitly selected condition list")
    if policy.get("unknown_eligibility") not in ("needs_clarification", "exclude"):
        gaps.append("Work-location unknown_eligibility must select needs_clarification or exclude")
    return gaps


def text(value):
    return isinstance(value, str) and bool(value.strip())


def exact_provenance(job, evidence, now, review=None):
    listing = url_identity(evidence.get("listing_url"))
    observed = timestamp(evidence.get("observed_at"))
    def paired(row):
        ids = {str(row.get(k)) for k in ("id", "canonical_opportunity_id", "canonical_recommendation_id") if row.get(k)}
        urls = {url_identity(row.get(k)) for k in ("url", "source_url", "canonical_project_url")} - {""}
        if str(evidence.get("opportunity_id")) in ids and listing in urls:
            return True
        return any(paired(alias) for key in ("source_aliases", "aliases", "identity_aliases") for alias in row.get(key, []) or [] if isinstance(alias, dict))
    if not (listing and paired(job) and text(evidence.get("evidence")) and observed and observed.timestamp() <= now.timestamp()):
        return False
    source = url_identity(evidence.get("source_url"))
    if source == listing:
        return True
    # A form restriction retains its actual form URL. Only an observed form
    # linked from this exact listing with matching employer/identifier qualifies.
    for route in ((review or {}).get("route"), job.get("route"), job.get("application_route")):
        if not isinstance(route, dict):
            continue
        status = route.get("status") or route.get("decision")
        checked = timestamp(route.get("checked_at") or route.get("verified_at"))
        identifier = norm(route.get("job_identifier") or route.get("job_id_in_page"))
        expected = {norm(job.get(k)) for k in ("id", "job_id", "source_job_id", "employer_requisition_id", "title")} - {""}
        if (status in {"form_observed", "exact_application_form_verified"}
                and source and source == url_identity(route.get("source_url") or route.get("exact_job_url") or route.get("url"))
                and url_identity(route.get("listing_url")) == listing and identifier in expected
                and norm(route.get("employer")) == norm(job.get("company") or job.get("employer_or_client"))
                and text(route.get("evidence")) and text(route.get("navigation_evidence"))
                and checked and checked.timestamp() <= now.timestamp()):
            return True
    return False


def assess(job, review, now, profile=None):
    policy = policy_for(profile)
    base = norm(policy["base_country"])
    selected_path = norm(policy["work_path"])
    configuration_gaps = policy_gaps(policy)
    raw = [row["work_eligibility"] for row in (job, review) if "work_eligibility" in row]
    assessments = []
    for value in raw:
        if value not in assessments:
            assessments.append(value)
    hard, gaps, levels, limitations = [], list(configuration_gaps), [], []
    if not assessments:
        gaps.append("Exact-opportunity work eligibility has not been reviewed")
    for item in assessments:
        if not isinstance(item, dict) or not exact_provenance(job, item, now, review):
            gaps.append("Work eligibility lacks exact ad/identity provenance, textual evidence or a valid observation time")
            continue
        path = item.get("work_path") if isinstance(item.get("work_path"), dict) else {}
        scope_matches = not configuration_gaps and norm(path.get("base_country")) == base and norm(path.get("work_path")) == selected_path
        if not scope_matches:
            gaps.append("Eligibility evidence does not match the current base country and work path")
            continue
        selected_path_supported = path.get("status") == "explicit" and text(path.get("evidence"))
        if path.get("status") == "unavailable" and text(path.get("evidence")):
            hard.append("Exact opportunity explicitly excludes the configured country/work path")
        elif not selected_path_supported:
            gaps.append("The configured country/work path is not explicitly supported for this opportunity")
        full_ad = item.get("full_ad_reviewed") is True and job.get("description_complete") is not False
        if not full_ad:
            gaps.append("Full exact advertisement has not been reviewed for work eligibility")
        basis = item.get("authorization_basis")
        supported_basis = basis in ("explicit_no_foreign_requirement", "not_stated_full_ad", "employer_confirmation") and text(item.get("authorization_evidence"))
        if not supported_basis:
            gaps.append("Foreign authorization/residency/relocation conditions remain unknown or ambiguous")
        if item.get("constraints_checked") is not True or not isinstance(item.get("constraints"), list):
            gaps.append("Mandatory work-location and authorization conditions have not been assessed")
            constraints = []
        else:
            constraints = item["constraints"]
        for condition in constraints:
            if not isinstance(condition, dict) or not text(condition.get("evidence")) or type(condition.get("mandatory")) is not bool:
                gaps.append("A work-eligibility condition lacks a supported mandatory/optional classification")
                continue
            if not condition["mandatory"]:
                continue
            country = norm(condition.get("country"))
            if len(country) != 2 or not country.isascii() or not country.isalpha() or country == "eu":
                gaps.append("Country/scope of a mandatory work condition is unresolved")
                continue
            if country == base:
                # This preference does not establish the candidate's domestic
                # citizenship/permit status; no foreign requirement is inferred.
                continue
            scope = condition.get("scope", "all_paths")
            if scope == "alternative_only":
                if selected_path_supported and full_ad and supported_basis and text(condition.get("alternative_path_evidence")):
                    continue
                gaps.append("Foreign alternative is not separated from a verified configured path")
                continue
            if scope != "all_paths":
                gaps.append("Applicability of a foreign work condition is unresolved")
                continue
            kind = condition.get("kind")
            if kind == "office_presence":
                kind = "office_only" if condition.get("office_only") is True else "travel"
            if kind in policy["exclude_required_foreign_conditions"]:
                hard.append("Required foreign " + str(kind) + " in " + str(condition.get("country")) + " conflicts with the configured country/work-path preference")
            else:
                gaps.append("Mandatory foreign travel or another condition needs role-specific eligibility evidence; no visa requirement inferred")
        if basis == "not_stated_full_ad":
            levels.append("full_ad_no_foreign_requirement_stated")
            limitations.append("No foreign requirement stated in the full ad; not employer confirmation or legal assurance")
        elif basis == "employer_confirmation":
            levels.append("employer_confirmation_recorded")
            limitations.append("Attributed employer confirmation; candidate citizenship/permits and legal status are not established")
        elif basis == "explicit_no_foreign_requirement":
            levels.append("explicit_role_statement")
            limitations.append("Role-specific statement; candidate citizenship/permits and legal status are not established")
    if gaps and policy.get("unknown_eligibility") == "exclude":
        hard.append("Configured policy excludes unresolved work eligibility")
    hard, gaps = list(dict.fromkeys(hard)), list(dict.fromkeys(gaps))
    return {"passed": not hard and not gaps, "decision": "excluded" if hard else "needs_clarification" if gaps else "eligible_path_supported",
            "hard_exclusions": hard, "gaps": gaps, "policy": policy,
            "evidence_level": levels[0] if levels and len(set(levels)) == 1 else "mixed" if levels else "unknown",
            "limitation": "; ".join(dict.fromkeys(limitations)) or "No work-authorization or citizenship facts inferred",
            "assessments": copy.deepcopy(assessments)}
