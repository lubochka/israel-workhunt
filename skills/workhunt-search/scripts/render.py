"""Render the local opportunity board. No sending, tracking pixels, or remote assets."""
import argparse
import datetime as dt
import json
from pathlib import Path
from scan import web_url
from profile_config import private_root, load_profile, safe_output
from records import load, read_store, display_job, related_records, application_state
from qualification import qualify, search_brief
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent


def effective_review(job, review, profile, now, found=None, applied=None, brief=None):
    return qualify(job, review, brief or search_brief(profile, now), now, found, applied)


def canonical_review(job):
    """Adapt known canonical fields conservatively; ambiguous historical claims stay unresolved."""
    review = dict(job.get("review") or {})
    for key in ("requirements", "publication", "publication_events", "degree_status", "degree_evidence", "cv_file", "duplicate_checked", "role", "stack", "geography", "full_description_read", "description_evidence"):
        if key in job and key not in review:
            review[key] = job[key]
    if isinstance(job.get("fit"), dict):
        fit = job["fit"]
        review.setdefault("requirements", fit.get("requirements", []))
        review.setdefault("reason", fit.get("evidence", ""))
    route = job.get("route") or job.get("application_route") or {}
    if isinstance(route, dict) and "route" not in review:
        route = dict(route)
        route.setdefault("source_url", route.get("exact_job_url") or route.get("url", ""))
        route.setdefault("checked_at", route.get("verified_at", ""))
        route.setdefault("job_identifier", route.get("job_id_in_page", ""))
        route["status"] = {"exact_application_form_verified": "form_observed", "qualified_login": "login_required"}.get(route.get("status"), route.get("status", "unverified"))
        review["route"] = route
    return review


def render(workdir, run=None, fixture=False, output=None, search_run_id=None):
    profile = load_profile(workdir)
    workdir = private_root(workdir)
    folder = workdir / ("fixture-runs" if fixture else "runs")
    explicit_scan_run = run is not None
    if run is None:
        candidates = sorted(p for p in folder.glob("*") if p.is_dir() and (p / "meta.json").exists())
        run = candidates[-1] if candidates else None
    else:
        run = Path(run).resolve()
        if run.parent != folder.resolve():
            raise ValueError("Run must belong to this workspace's selected runs directory")
    meta = load(run / "meta.json", {}) if run else {}
    if meta and bool(meta.get("fixture_mode")) != fixture:
        raise ValueError("Fixture and live runs must not be mixed")
    found, applied = ({"opportunities": [], "search_runs": []}, {"records": []}) if fixture else read_store(workdir)
    discovered = load(run / "hits.json", []) if run else []
    # Canonical identities take precedence over legacy records and scan snapshots.
    jobs = [display_job(row) for row in found["opportunities"]]
    manual = [] if fixture else load(workdir / "manual-opportunities.json", [])
    for item in manual:
        if not {"id", "company", "title", "url", "description"}.issubset(item) or not web_url(item["url"]):
            raise ValueError("Legacy manual opportunity needs identity, company, title, HTTP(S) URL and description")
    for item in discovered + manual:
        if not related_records(item, jobs):
            jobs.append(display_job(item))
    reviews = {} if fixture else load(workdir / "reviews.json", {})
    legacy_applications = {} if fixture else load(workdir / "applications.json", {})
    now = dt.datetime.now(ZoneInfo(profile["timezone"]))
    canonical_runs = found.get("search_runs", [])
    selected_id = search_run_id or found.get("active_run_id")
    selected_run = next((r for r in canonical_runs if r.get("id") == selected_id), None) if selected_id else (canonical_runs[-1] if canonical_runs else None)
    if selected_id and selected_run is None:
        raise ValueError("Selected canonical search run does not exist")
    saved_brief = meta.get("search_brief")
    if selected_run and not explicit_scan_run:
        saved_brief = {**profile.get("search_brief", {}), **selected_run.get("search_brief", {}),
                       **{k: selected_run[k] for k in ("window_start", "window_end", "requested_minimum", "run_type") if k in selected_run}}
    brief = search_brief(profile, now, saved_brief)
    for j in jobs:
        review = {**reviews.get(j["id"], {}), **canonical_review(j)}
        j["review"] = effective_review(j, review, profile, now, found, applied, brief)
        records = related_records(j, applied["records"])
        submission = next((r for r in records if r.get("submission") or r.get("submission_status")), None)
        j["application_state"] = application_state(submission or j.get("submission") or legacy_applications.get(j["id"], {}), now)
        if j["application_state"] == "not_recorded" and j.get("application_packet"):
            j["application_state"] = "prepared"
        j.pop("source_payload", None)
    qualified_count = sum(j["review"]["qualified"] for j in jobs)
    data = {"name": profile["name"], "headline": profile["headline"], "tracks": {k: v["label"] for k, v in profile["tracks"].items()},
            "fixture_mode": fixture, "meta": meta, "search_brief": brief,
            "selected_run": {k: selected_run[k] for k in ("id", "status", "qualified_count", "actual_qualified_count", "requested_minimum", "window_start", "window_end") if k in selected_run} if selected_run else None,
            "qualified_count": qualified_count,
            "shortfall": max(0, brief["requested_minimum"] - qualified_count) if brief["requested_minimum"] is not None else None, "jobs": jobs, "failed": load(run / "failed.json", []) if run else [],
            "changes": load(run / "changes.json", []) if run else [], "manual_sources": profile.get("manual_sources", [])}
    text = (HERE.parent / "assets" / "page.html").read_text(encoding="utf-8")
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    text = text.replace("/*__DATA__*/", blob)
    output = Path(output).resolve() if output else workdir / ("fixture-preview.html" if fixture else "jobs.html")
    output = safe_output(workdir, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    if run and output.parent == workdir:
        (run / "jobs.html").write_text(text, encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workdir", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--output", type=Path, help="Optional local preview path; never changes canonical records")
    parser.add_argument("--search-run", help="Select a canonical fixed-window search run by ID")
    args = parser.parse_args()
    print(render(args.workdir, args.run, args.fixture, args.output, args.search_run))
