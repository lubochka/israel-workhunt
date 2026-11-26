"""One evidence gate used by the collector, renderer and local application packets."""
import copy
import datetime as dt
from fractions import Fraction
import re
from zoneinfo import ZoneInfo
from records import history_decision, norm, timestamp, url_identity

LOGIN_LABEL = "Login required; not verified beyond this point"


def normalize_route(value):
    route = copy.deepcopy(value) if isinstance(value, dict) else {}
    recorded_status = route.get("status") or route.get("decision")
    route["status"] = {"exact_application_form_verified": "form_observed", "qualified_login": "login_required"}.get(recorded_status, recorded_status)
    # The legacy qualified-login decision explicitly encoded the exact-vacancy
    # acceptance conclusion. It still needs recorded evidence.
    if recorded_status == "qualified_login":
        route.setdefault("exact_vacancy_accepting_applications", True)
    route.setdefault("source_url", route.get("exact_job_url") or route.get("url"))
    route.setdefault("checked_at", route.get("verified_at"))
    route.setdefault("job_identifier", route.get("job_id_in_page"))
    return route


def route_evidence_recorded(value, allow_proposal=True):
    """Saved route evidence only; freshness and exact linkage are separate checks."""
    route = normalize_route(value)
    return bool(route.get("evidence")) and (
        route.get("status") == "form_observed"
        or allow_proposal and route.get("status") == "proposal_observed"
        or route.get("status") == "login_required" and route.get("exact_vacancy_accepting_applications") is True)


EXTENDED_SOURCE_GROUPS = {"employer_registry", "techmap"}


def fixed_window(end, hours, start=None, timezone=None):
    if type(hours) not in {int, float} or hours <= 0:
        raise ValueError("Freshness window hours must be positive")
    expected = (end.astimezone(dt.timezone.utc) - dt.timedelta(hours=hours)).astimezone(ZoneInfo(timezone) if isinstance(timezone, str) else timezone or end.tzinfo)
    if start is not None and (timestamp(start) is None or timestamp(start).timestamp() != expected.timestamp()):
        raise ValueError("Saved source window does not match its hours and shared anchor")
    return {"hours": hours, "window_start": start if start is not None else expected.isoformat(), "window_end": end.isoformat()}


RUN_BRIEF_FIELDS = ("window_start", "window_end", "source_windows", "requested_minimum", "run_type", "manual_source_freshness_hours", "manual_freshness_policy", "timezone")


def run_brief_snapshot(run):
    saved = copy.deepcopy(run.get("search_brief") or {})
    for key in RUN_BRIEF_FIELDS:
        if key in run:
            saved[key] = copy.deepcopy(run[key])
    return saved


def recorded_run_context(run):
    if "boards_attempted" in run and "fixture_mode" in run:
        return "collector"
    saved = run_brief_snapshot(run)
    if run.get("execution_context") or saved.get("execution_context"):
        return run.get("execution_context") or saved["execution_context"]
    if saved.get("run_type") in {"notification", "assessment", "fixture"}:
        return saved["run_type"]
    # Recorded source windows are enacted policy, unlike dormant preferences
    # copied by the old collector's profile-derived helper.
    return "manual" if saved.get("source_windows") else "unresolved"


def recover_brief_context(saved, runs):
    matches = [run for run in runs if run.get("search_brief") == saved or run_brief_snapshot(run) == saved]
    provenance = {"status": "unresolved_unmatched_legacy", "matching_run_ids": [run.get("id") for run in matches]}
    if not matches:
        return saved, "unresolved", provenance
    candidates = [(run_brief_snapshot(run), recorded_run_context(run)) for run in matches]
    # Canonical metadata cannot silently revise supplied bounds or policy.
    conflict = any(any(key in saved and value.get(key) != saved[key] for key in RUN_BRIEF_FIELDS) for value, _ in candidates)
    policies = [(context, {key: value.get(key) for key in RUN_BRIEF_FIELDS}) for value, context in candidates]
    if conflict or any(policy != policies[0] for policy in policies[1:]):
        provenance["status"] = "unresolved_conflicting_canonical_evidence"
        return saved, "unresolved", provenance
    value, context = candidates[0]
    provenance["status"] = "canonical_snapshot_match" if context != "unresolved" else "unresolved_canonical_context"
    return value, context, provenance


def search_brief(profile, now, saved=None, execution_context=None, saved_runs=None):
    # A saved run is a policy snapshot. Never merge today's profile into it.
    config = copy.deepcopy(saved if saved is not None else profile.get("search_brief") or {})
    if not isinstance(config, dict):
        raise ValueError("Search brief must be an object")
    recorded_marker = config.get("execution_context") if saved is not None else None
    provenance = {"status": "explicit_execution_context" if execution_context else "new_profile" if saved is None else "recorded_context" if recorded_marker else "recorded_run_type" if config.get("run_type") in {"notification", "assessment", "fixture"} else "unresolved_legacy_context"}
    recovered_context = None
    if saved is not None and not recorded_marker and config.get("run_type", "manual") == "manual" and execution_context is None and saved_runs is not None:
        config, recovered_context, provenance = recover_brief_context(config, saved_runs)
    run_type = config.get("run_type", "manual")
    if run_type not in {"manual", "notification", "assessment", "fixture"}:
        raise ValueError("Unknown search run type")
    context = execution_context or recorded_marker or (config.get("execution_context") if saved is None else None) or recovered_context or (run_type if saved is None or run_type != "manual" else "unresolved")
    if context not in {"manual", "collector", "notification", "assessment", "fixture", "unresolved"}:
        raise ValueError("Unknown qualification execution context")
    minimum = config.get("requested_minimum", None)
    if minimum is not None and (type(minimum) is not int or minimum < 0):
        raise ValueError("requested_minimum must be a nonnegative integer or null")
    cap = config.get("result_cap")
    if cap is not None and (type(cap) is not int or cap < 1 or minimum is not None and cap < minimum):
        raise ValueError("A result cap cannot be smaller than the requested minimum")
    for key in ("window_start", "window_end"):
        if key in config and timestamp(config[key]) is None:
            raise ValueError("Invalid saved " + key)
    saved_state = saved is not None and any(key in config for key in ("window_start", "window_end", "source_windows"))
    zone_name = config.get("timezone") if saved_state else config.get("timezone", profile["timezone"])
    recorded_end = timestamp(config.get("window_end"))
    # Legacy snapshots without an IANA name retain their recorded offset. A
    # current profile zone must not change a historical policy snapshot.
    zone = ZoneInfo(zone_name) if zone_name else recorded_end.tzinfo if recorded_end else now.tzinfo
    end = recorded_end or now.astimezone(zone)
    manual = context == "manual" and run_type == "manual"
    start = timestamp(config.get("window_start"))
    preserve_base = manual or context == "unresolved" and run_type == "manual"
    hours = (end.timestamp() - start.timestamp()) / 3600 if preserve_base and start else 24
    base = fixed_window(end, hours, config.get("window_start") if preserve_base and start else None, zone)
    windows = {"other": base}
    if manual:
        if "source_windows" in config:
            if not isinstance(config["source_windows"], dict):
                raise ValueError("Saved source_windows must be an object")
            for group, value in config["source_windows"].items():
                if not isinstance(value, dict):
                    raise ValueError("Invalid saved source window")
                for bound in ("window_start", "window_end"):
                    if bound in value and timestamp(value[bound]) is None:
                        raise ValueError("Saved source window has an invalid bound")
                anchor = timestamp(value.get("window_end", end.isoformat()))
                if anchor is None or anchor.timestamp() != end.timestamp():
                    raise ValueError("Saved source window has a different or invalid anchor")
                windows[group] = fixed_window(end, value.get("hours"), value.get("window_start"), zone)
            if windows["other"]["window_start"] != base["window_start"] and timestamp(windows["other"]["window_start"]).timestamp() != timestamp(base["window_start"]).timestamp():
                raise ValueError("Saved default source window contradicts recorded base bounds")
        elif saved is None or recorded_marker == "manual":
            mapping = config.get("manual_source_freshness_hours", {})
            if not isinstance(mapping, dict):
                raise ValueError("manual_source_freshness_hours must be an object")
            for group in EXTENDED_SOURCE_GROUPS & mapping.keys():
                windows[group] = fixed_window(end, mapping[group], timezone=zone)
    if context == "unresolved" and "recorded_source_windows" not in config:
        # Null records absence, so generated effective bounds cannot become
        # supposed historical evidence when this normalized snapshot is read again.
        config["recorded_source_windows"] = copy.deepcopy(config.get("source_windows"))
    # A normalized snapshot carries original evidence across JSON/packet reloads.
    # Preserve it without treating that provenance as an execution marker.
    original_provenance = config.get("context_provenance")
    return {**config, "run_type": run_type, "execution_context": context,
            "context_provenance": copy.deepcopy(original_provenance) if isinstance(original_provenance, dict) else provenance,
            "context_resolution": {**provenance, "execution_context": context}, "requested_minimum": minimum, "result_cap": cap,
            "timezone": zone_name, "language": profile.get("language"), "window_start": base["window_start"], "window_end": end.isoformat(), "source_windows": windows,
            "tracks": config.get("tracks", list(profile["tracks"])),
            "required_stack": config.get("required_stack", []),
            "eligible_countries": profile["eligible_countries"],
            "limited_experience": profile.get("limited_experience", {}),
            "degree_policy": profile.get("degree_policy", {}),
            "completed_qualifications": [str(item.get("id") or item.get("qualification") or item.get("name")) for item in profile.get("education", []) if item.get("completed") is True and item.get("evidence_ids")],
            "freshness_events": ["original", "first_published", "refresh", "repost", "last_published"],
            "destination": config.get("destination", "current_chat"),
            "manual_source_freshness_hours": config.get("manual_source_freshness_hours", {}),
            "manual_freshness_policy": config.get("manual_freshness_policy", {}),
            "authorized_methods": [],
            "authorized_actions": [],
            "silence_if_zero": run_type == "notification"}


def select_search_run(found, selected_id=None):
    runs = found.get("search_runs", [])
    selected_id = selected_id or found.get("active_run_id")
    run = next((row for row in runs if row.get("id") == selected_id), None) if selected_id else (runs[-1] if runs else None)
    if selected_id and run is None:
        raise ValueError("Selected canonical search run does not exist")
    return run


def brief_from_run(profile, now, run):
    saved = run_brief_snapshot(run)
    brief = search_brief(profile, now, saved, execution_context=recorded_run_context(run))
    resolution = {"status": "canonical_run" if brief["execution_context"] != "unresolved" else "unresolved_canonical_context", "matching_run_ids": [run.get("id")]}
    if not isinstance(saved.get("context_provenance"), dict):
        brief["context_provenance"] = resolution
    brief["context_resolution"] = {**resolution, "execution_context": brief["execution_context"]}
    return brief


def source_window(job, review, brief, now):
    end = timestamp(brief["window_end"])
    manual = brief.get("run_type") == "manual" and brief.get("execution_context", "manual") == "manual"
    base = brief.get("source_windows", {}).get("other") or {"window_start": brief["window_start"], "window_end": brief["window_end"], "hours": (end.timestamp() - timestamp(brief["window_start"]).timestamp()) / 3600}
    if brief.get("execution_context") == "unresolved" and brief.get("run_type") == "manual":
        return {**copy.deepcopy(base), "group": "other", "membership_verified": False, "fallback_reason": "Historical context unresolved; recorded base bounds retained without source widening"}
    if not manual:
        return {**fixed_window(end, 24, timezone=brief.get("timezone")), "group": "other", "membership_verified": False, "fallback_reason": "Manual source widening does not apply to this execution context"}
    membership = review.get("source_membership", job.get("source_membership"))
    reason = "No structured exact-opportunity source membership; using recorded default bounds"
    if isinstance(membership, dict):
        group = membership.get("group")
        observed = timestamp(membership.get("observed_at"))
        evidence = membership.get("evidence")
        # ID and URL must belong to the same explicit identity object. Do not
        # combine one cross-post's ID with another cross-post's listing URL.
        def paired(row):
            identifiers = {str(row.get(key)) for key in ("id", "canonical_opportunity_id", "canonical_recommendation_id") if row.get(key)}
            urls = {url_identity(row.get(key)) for key in ("url", "source_url", "canonical_project_url")} - {""}
            if str(membership.get("opportunity_id")) in identifiers and url_identity(membership.get("listing_url")) in urls:
                return True
            return any(paired(alias) for key in ("source_aliases", "aliases", "identity_aliases") for alias in row.get(key, []) or [] if isinstance(alias, dict))
        valid = isinstance(group, str) and group in EXTENDED_SOURCE_GROUPS and isinstance(evidence, str) and bool(evidence.strip()) and bool(url_identity(membership.get("source_url"))) and observed is not None and observed.timestamp() <= now.timestamp() and paired(job)
        if valid:
            window = brief.get("source_windows", {}).get(group)
            if window:
                return {**copy.deepcopy(window), "group": group, "membership_verified": True, "membership_evidence": copy.deepcopy(membership)}
            reason = "Source membership evidenced, but the saved policy has no extended window for this group"
        else:
            reason = "Unsupported source membership, identity, provenance or observation; using recorded default bounds"
    return {**copy.deepcopy(base), "group": "other", "membership_verified": False, "fallback_reason": reason}


def score_requirements(requirements):
    distinct = {}
    for item in requirements if isinstance(requirements, list) else []:
        if not isinstance(item, dict) or item.get("mandatory", True) is False:
            continue
        key = norm(item.get("criterion_id") or item.get("requirement"))
        if not key:
            key = "unidentified:" + str(len(distinct))
        supported = item.get("met") is True and bool(item.get("evidence")) or (item.get("alternative_explicitly_accepted") is True and item.get("alternative_met") is True and bool(item.get("alternative_evidence")))
        if key not in distinct:
            distinct[key] = {**item, "supported": supported}
        elif not supported:
            # Contradictory duplicate evidence stays unresolved, not cherry-picked.
            distinct[key]["supported"] = False
    rows = list(distinct.values())
    supported = sum(r["supported"] for r in rows)
    total = len(rows)
    return {"supported": supported, "total": total, "percentage": 100 * supported / total if total else None,
            "passes": bool(total and Fraction(supported, total) >= Fraction(3, 4)),
            "gaps": [r.get("requirement", "Unidentified criterion") for r in rows if not r["supported"]], "criteria": rows}


def freshness(review, brief, job=None, now=None):
    window = source_window(job or {}, review, brief, now or dt.datetime.now(dt.timezone.utc))
    start, end = timestamp(window["window_start"]), timestamp(window["window_end"])
    events = review.get("publication_events") or [review.get("publication", {})]
    for event in events:
        kind = event.get("kind")
        if kind not in brief["freshness_events"] or not event.get("evidence") or not url_identity(event.get("source_url")):
            continue
        if kind in {"refresh", "repost", "last_published"} and event.get("genuine_publication_event") is not True:
            continue
        lower = timestamp(event.get("at") or event.get("date") or event.get("interval_start"))
        upper = timestamp(event.get("interval_end")) or lower
        # Date-only evidence supports a whole local day, never an invented hour.
        if not lower and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(event.get("date", ""))) and event.get("timezone"):
            try:
                lower = dt.datetime.combine(dt.date.fromisoformat(event["date"]), dt.time(), ZoneInfo(event["timezone"]))
                upper = lower + dt.timedelta(days=1)
            except (ValueError, KeyError):
                continue
        if lower and upper and start.timestamp() <= lower.timestamp() <= upper.timestamp() <= end.timestamp():
            return {"passed": True, "qualifying_event": copy.deepcopy(event), "window": window}
    return {"passed": False, "reason": "No supported publication/refresh interval wholly inside the applicable fixed window", "window": window}


def qualify(job, review, brief, now, found=None, applied=None, history_index=None):
    review = copy.deepcopy(review or {})
    score = score_requirements(review.get("requirements", []))
    hard = []
    if job.get("active") is False:
        hard.append("Source explicitly marks this posting inactive")
    if review.get("degree_status") == "mandatory_no_alternative":
        hard.append("Mandatory degree without an accepted alternative")
    for item in score["criteria"]:
        technology = norm(item.get("technology"))
        years = item.get("minimum_years")
        cap = brief.get("limited_experience", {}).get(technology)
        if years is None:
            match = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*years?", str(item.get("requirement", "")), re.I)
            years = float(match[1]) if match else 0
        if isinstance(cap, (int, float)) and isinstance(years, (int, float)) and years > cap and not item["supported"] and not (item.get("alternative_met") is True and item.get("alternative_evidence")):
            hard.append("Requirement exceeds supported technology duration: " + item.get("requirement", technology))
    route = normalize_route(review.get("route"))
    if route.get("status") == "closed":
        hard.append("Application route recorded as closed")
    deadline = timestamp(job.get("deadline"))
    if deadline and deadline < now:
        hard.append("Recorded application deadline has passed")
    history = history_decision(job, found or {"opportunities": []}, applied or {"records": []}, history_index)
    history_known = found is not None and applied is not None and found.get("_history_available", True) and applied.get("_history_available", True)
    role = review.get("role") if isinstance(review.get("role"), dict) else {}
    stack = review.get("stack") if isinstance(review.get("stack"), dict) else {}
    geography = review.get("geography") if isinstance(review.get("geography"), dict) else {}
    degree = review.get("degree_status")
    policy = brief.get("degree_policy", {})
    qualification_id = str(review.get("degree_qualification") or "")
    degree_pass = degree in {"preferred", "not_stated"} or (
        degree == "experience_equivalent" and policy.get("accept_experience_alternative") is True
    ) or (
        degree == "mandatory_met" and qualification_id in policy.get("accepted_qualifications", [])
        and qualification_id in brief.get("completed_qualifications", [])
    )
    description = bool(job.get("description_complete") is not False and (job.get("description") or review.get("description_evidence")) and (review.get("full_description_read") is True or job.get("full_description_read") is True))
    checked = timestamp(route.get("checked_at"))
    identity = norm(route.get("job_identifier"))
    expected = {norm(job.get(k)) for k in ("id", "job_id", "source_job_id", "employer_requisition_id", "title")} - {""}
    specific = identity in expected and bool(route.get("evidence")) and bool(url_identity(route.get("source_url")))
    listing_urls = {url_identity(job.get(k)) for k in ("url", "source_url")} - {""}
    linked = url_identity(route.get("source_url")) in listing_urls or (
        url_identity(route.get("listing_url")) in listing_urls
        and norm(route.get("employer")) == norm(job.get("company") or job.get("employer_or_client"))
        and bool(route.get("navigation_evidence")))
    specific = specific and linked
    current = checked is not None and 0 <= (now.astimezone(dt.timezone.utc) - checked.astimezone(dt.timezone.utc)).total_seconds() <= 24 * 3600
    route_pass = specific and current and route_evidence_recorded(route, allow_proposal=job.get("type") == "project")
    if route.get("status") == "login_required":
        route["label"] = {"he": "דורש התחברות; לא אומת מעבר לכך", "ru": "Требуется вход; дальнейшая проверка не выполнена"}.get(brief.get("language"), LOGIN_LABEL)
    fresh = freshness(review, brief, job, now)
    checks = {
        "description": description,
        "cv_fit": score["passes"],
        "role": role.get("track") in brief["tracks"] and role.get("confirmed") is True and bool(role.get("evidence")),
        "stack": all(stack.get(k) is True for k in brief["required_stack"]) and bool(stack.get("evidence")),
        "geography": geography.get("eligible") is True and bool(geography.get("evidence")) and bool({norm(c) for c in geography.get("eligible_from", [])} & {norm(c) for c in brief["eligible_countries"]}),
        "education": degree_pass and bool(review.get("degree_evidence")),
        "route": bool(route_pass), "freshness": fresh["passed"],
        "history": history_known and history["newness_qualified"] and review.get("duplicate_checked") is True,
        "cv_selection": bool(review.get("cv_file")),
    }
    gaps = [key + " evidence missing or does not pass" for key, passed in checks.items() if not passed]
    requested = review.get("fit", "unreviewed")
    qualified = not hard and all(checks.values()) and requested != "exclude"
    state = history["state"] if history["state"] != "new" else "excluded" if hard or requested == "exclude" else "qualified_new" if qualified else "needs_clarification"
    fit = "exclude" if state in {"suppressed", "already_applied", "previously_reported", "excluded"} else "strong" if qualified else "unreviewed" if requested == "unreviewed" else "clarify"
    return {**review, "fit": fit, "decision": state, "qualified": qualified and state == "qualified_new",
            "score": score, "checks": checks, "history_check": history, "freshness_check": fresh,
            "hard_exclusions": hard, "verification_gaps": hard + gaps, "route": route}
