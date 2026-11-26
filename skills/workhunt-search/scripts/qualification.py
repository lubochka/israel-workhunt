"""One evidence gate used by the collector, renderer and local application packets."""
import copy
import datetime as dt
from fractions import Fraction
import re
from zoneinfo import ZoneInfo
from records import history_decision, norm, timestamp, url_identity

LOGIN_LABEL = "Login required; not verified beyond this point"


def search_brief(profile, now, saved=None):
    config = copy.deepcopy(saved or profile.get("search_brief") or {})
    run_type = config.get("run_type", "manual")
    if run_type not in {"manual", "notification", "assessment", "fixture"}:
        raise ValueError("Unknown search run type")
    minimum = config.get("requested_minimum", None)
    if minimum is not None and (type(minimum) is not int or minimum < 0):
        raise ValueError("requested_minimum must be a nonnegative integer or null")
    cap = config.get("result_cap")
    if cap is not None and (type(cap) is not int or cap < 1 or minimum is not None and cap < minimum):
        raise ValueError("A result cap cannot be smaller than the requested minimum")
    end = timestamp(config.get("window_end")) or now.astimezone(ZoneInfo(profile["timezone"]))
    start = timestamp(config.get("window_start")) or (end.astimezone(dt.timezone.utc) - dt.timedelta(hours=24)).astimezone(ZoneInfo(profile["timezone"]))
    if end.astimezone(dt.timezone.utc) - start.astimezone(dt.timezone.utc) != dt.timedelta(hours=24):
        raise ValueError("The active freshness window must be exactly 24 hours")
    return {**config, "run_type": run_type, "requested_minimum": minimum, "result_cap": cap,
            "timezone": profile["timezone"], "language": profile.get("language"), "window_start": start.isoformat(), "window_end": end.isoformat(),
            "tracks": config.get("tracks", list(profile["tracks"])),
            "required_stack": config.get("required_stack", []),
            "eligible_countries": profile["eligible_countries"],
            "limited_experience": profile.get("limited_experience", {}),
            "degree_policy": profile.get("degree_policy", {}),
            "completed_qualifications": [str(item.get("id") or item.get("qualification") or item.get("name")) for item in profile.get("education", []) if item.get("completed") is True and item.get("evidence_ids")],
            "freshness_events": ["original", "first_published", "refresh", "repost", "last_published"],
            "destination": config.get("destination", "current_chat"),
            "authorized_methods": [],
            "authorized_actions": [],
            "silence_if_zero": run_type == "notification"}


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


def freshness(review, brief):
    start, end = timestamp(brief["window_start"]), timestamp(brief["window_end"])
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
            return {"passed": True, "qualifying_event": copy.deepcopy(event)}
    return {"passed": False, "reason": "No supported publication/refresh interval wholly inside the fixed 24-hour window"}


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
    route = review.get("route") if isinstance(review.get("route"), dict) else {}
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
    route_pass = specific and current and (route.get("status") == "form_observed" or route.get("status") == "login_required" and route.get("exact_vacancy_accepting_applications") is True)
    if route.get("status") == "login_required":
        route["label"] = {"he": "דורש התחברות; לא אומת מעבר לכך", "ru": "Требуется вход; дальнейшая проверка не выполнена"}.get(brief.get("language"), LOGIN_LABEL)
    if job.get("type") == "project" and route.get("status") == "proposal_observed":
        route_pass = specific and current
    fresh = freshness(review, brief)
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
