"""Render the local opportunity board. No sending, tracking pixels, or remote assets."""
import argparse
import datetime as dt
import json
from pathlib import Path
from scan import web_url
from profile_config import private_root, load_profile, safe_output
from records import load, read_store, display_job, related_records, application_evidence, application_state
from qualification import brief_from_run, normalize_route, qualify, search_brief, select_search_run
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent


def effective_review(job, review, profile, now, found=None, applied=None, brief=None):
    return qualify(job, review, brief or search_brief(profile, now), now, found, applied, profile=profile)


def canonical_review(job):
    """Adapt known canonical fields conservatively; ambiguous historical claims stay unresolved."""
    review = dict(job.get("review") or {})
    for key in ("requirements", "publication", "publication_events", "source_membership", "degree_status", "degree_evidence", "cv_file", "duplicate_checked", "role", "stack", "project_scope", "geography", "full_description_read", "description_evidence"):
        if key in job and key not in review:
            review[key] = job[key]
    if isinstance(job.get("fit"), dict):
        fit = job["fit"]
        review.setdefault("requirements", fit.get("requirements", []))
        review.setdefault("reason", fit.get("evidence", ""))
    route = job.get("route") or job.get("application_route") or {}
    if isinstance(route, dict) and "route" not in review:
        review["route"] = normalize_route(route)
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
    selected_run = select_search_run(found, search_run_id)
    if selected_run and not explicit_scan_run:
        brief = brief_from_run(profile, now, selected_run)
    elif run:
        # Run-directory metadata always describes collector execution, including
        # legacy scans written before execution_context existed.
        saved_brief = dict(meta.get("search_brief") or {})
        saved_brief.setdefault("window_end", meta.get("checked_at", now.isoformat()))
        brief = search_brief(profile, now, saved_brief, execution_context="collector")
    else:
        brief = search_brief(profile, now)
    for j in jobs:
        review = {**reviews.get(j["id"], {}), **canonical_review(j)}
        j["review"] = effective_review(j, review, profile, now, found, applied, brief)
        records = related_records(j, applied["records"])
        candidates = records + ([j] if any(key in j for key in ("submission", "submission_status", "submission_events", "submission_snapshots")) else [])
        snapshots = [evidence["latest"] for evidence in (application_evidence(row, now) for row in candidates) if evidence["latest"] is not None]
        submission = {"submission_snapshots": snapshots} if snapshots else candidates[0] if candidates else legacy_applications.get(j["id"], {})
        j["application_state"] = application_state(submission, now)
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
    output.write_bytes(text.encode("utf-8"))
    if run and output.parent == workdir:
        (run / "jobs.html").write_bytes(text.encode("utf-8"))
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
