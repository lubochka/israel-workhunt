"""Adapted from Shahar Bar's supplied Job Hunt Kit. Public GETs only; no applications.

Run: python scan.py WORKDIR --network [--limit-boards N]
Test data: python scan.py WORKDIR --fixtures FIXTURE.json
"""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.parse as up
import urllib.request as ur
import uuid
from zoneinfo import ZoneInfo
from profile_config import load_profile, private_root, validate_profile
from records import read_store, history_decision, merge_discovery, save as save_canonical
from qualification import search_brief, qualify
from source_registry import board_from, load_boards, record_source_checks, TECHMAP_CATEGORIES
from adapters import FetchResult, smart_normalize, smart_fetch, techmap_parse, recruitee_parse, deduplicate_discoveries

HERE = Path(__file__).resolve().parent
DIRECTORY = "https://www.shaharpolak.com/api/hiring.json"


def load(path, default=None):
    return json.loads(Path(path).read_text(encoding="utf-8-sig")) if Path(path).exists() else default


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def plain(value):
    class Text(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
        def handle_data(self, data):
            self.parts.append(data)
        def handle_starttag(self, tag, attrs):
            if tag in {"p", "li", "br", "div", "h1", "h2", "h3"}:
                self.parts.append("\n")
        def handle_endtag(self, tag):
            if tag in {"p", "li", "div"}:
                self.parts.append("\n")
    value = value or ""
    for _ in range(3):
        decoded = html.unescape(value)
        if decoded == value:
            break
        value = decoded
    parser = Text()
    parser.feed(value)
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in "".join(parser.parts).splitlines() if line.strip())


def web_url(value):
    p = up.urlsplit(str(value or ""))
    return str(value) if p.scheme in ("https", "http") and p.hostname and not p.username else ""


def get(url):
    if not web_url(url):
        raise ValueError("Expected a public HTTP(S) URL")
    req = ur.Request(url, headers={"User-Agent": "Workhunt/1.0 (public job-board reader)"})
    with ur.urlopen(req, timeout=30) as response:
        return response.read(12_000_001).decode("utf-8")


def normalize(board, rows):
    if board["provider"] == "smartrecruiters":
        return smart_normalize(board, rows, plain)
    if not isinstance(rows, list):
        raise ValueError("API response has no job array")
    result = []
    for j in rows:
        if not isinstance(j, dict):
            raise ValueError("Job is not an object")
        provider = board["provider"]
        published = updated = last_published = deadline = ""
        if provider == "greenhouse":
            if "internal_job_id" in j and j["internal_job_id"] is None:
                continue  # A prospect/talent-pool post is not a normal requisition.
            title, url, apply_url = j["title"], j["absolute_url"], ""
            loc = (j.get("location") or {}).get("name", "")
            text = plain(j.get("content", ""))
            updated, published, deadline = j.get("updated_at", ""), j.get("first_published", ""), j.get("application_deadline", "")
            ident = j["id"]
            workplace = ""
        elif provider == "ashby":
            if j.get("isListed") is False:
                continue
            title, url, apply_url = j["title"], j["jobUrl"], j.get("applyUrl", "")
            loc = " | ".join(str(x) for x in [j.get("location", "")] + [x.get("location", "") for x in j.get("secondaryLocations", [])] if x)
            text = j.get("descriptionPlain") or plain(j.get("descriptionHtml", ""))
            last_published = j.get("publishedAt", "")
            ident = j.get("id") or url
            workplace = j.get("workplaceType", "")
        elif provider == "lever":
            title, url, apply_url = j["text"], j["hostedUrl"], j.get("applyUrl", "")
            cats = j.get("categories") or {}
            loc = " | ".join(dict.fromkeys(str(x) for x in [cats.get("location", ""), j.get("country", "")] + cats.get("allLocations", []) if x))
            text = "\n".join([j.get("descriptionPlain") or plain(j.get("description", ""))] +
                             [plain(x.get("text", "")) + ": " + plain(x.get("content", "")) for x in j.get("lists", [])] +
                             [j.get("additionalPlain") or plain(j.get("additional", ""))])
            ident, workplace = j["id"], j.get("workplaceType", "")
        else:
            title = j.get("name", "")
            url = j.get("url_comeet_hosted_page") or j.get("url_active_page") or ""
            apply_url = ""
            place = j.get("location") or {}
            loc = " | ".join(str(place.get(k, "")) for k in ("name", "city", "country") if place.get(k))
            text = "\n".join(plain(x.get("name", "")) + ": " + plain(x.get("value", "")) for x in j.get("details", []))
            updated, ident, workplace = j.get("time_updated", ""), j.get("uid") or url, j.get("workplace_type", "")
            if not title or not url or not text.strip(": \n"):
                raise ValueError("Incomplete Comeet details; cannot treat this board as successfully read")
        if not web_url(url):
            raise ValueError("Job has no safe public URL")
        if not ident:
            ident = hashlib.sha256(url.encode()).hexdigest()[:20]
        result.append({"id": f"{board['key']}:{ident}", "job_id": str(ident), "board_key": board["key"],
                       "provider": provider, "company": board["company"], "title": title, "url": url,
                       "apply_url": web_url(apply_url), "location": loc, "description": text,
                       "first_published_at": published or "", "last_published_at": last_published or "",
                       "updated_at": updated or "", "deadline": deadline or "", "work_model_stated": workplace or "unknown",
                       "application_status": "listing_only", "source": "public_ats", "source_payload": j,
                       "country_stated": j.get("country", ""),
                       "employment_type": j.get("employmentType") or (j.get("categories") or {}).get("commitment", "")})
    return result


def fetch(board):
    p, tenant, region = board["provider"], board["tenant"], board["region"]
    if p == "smartrecruiters":
        return smart_fetch(board, get, plain)
    if p == "techmap":
        return techmap_parse(board, get(board["url"]))
    if p == "recruitee":
        # Conditional documented public XML only. Never fall back to token-protected JSON.
        url = board["url"] if board["url"].endswith(".xml") else f"https://{tenant}.recruitee.com/api/feeds/offers.xml"
        return recruitee_parse(board, get(url), plain)
    if p == "greenhouse":
        host = "boards-api.eu.greenhouse.io" if region == "eu" else "boards-api.greenhouse.io"
        rows = json.loads(get(f"https://{host}/v1/boards/{tenant}/jobs?content=true"))["jobs"]
    elif p == "ashby":
        rows = json.loads(get(f"https://api.ashbyhq.com/posting-api/job-board/{tenant}"))["jobs"]
    elif p == "lever":
        host = "api.eu.lever.co" if region == "eu" else "api.lever.co"
        rows = json.loads(get(f"https://{host}/v0/postings/{tenant}?mode=json"))
    else:
        url = board["url"]
        if "/careers-api/" in url:
            parts = up.urlsplit(url)
            query = up.parse_qs(parts.query)
            query["details"] = ["true"]
            path = parts.path.rstrip("/")
            if not path.endswith("/positions"):
                path += "/positions"
            url = up.urlunsplit((parts.scheme, parts.netloc, path, up.urlencode(query, doseq=True), ""))
        else:
            page = get(url)
            tok = re.search(r'["\']token["\']\s*:\s*["\']([A-Za-z0-9_-]+)["\']', page)
            if not tok:
                raise ValueError("Comeet public careers token not found; manual verification required")
            url = f"https://www.comeet.co/careers-api/2.0/company/{tenant}/positions?" + up.urlencode({"token": tok[1], "details": "true"})
        rows = json.loads(get(url))
    return normalize(board, rows)


def classify(job, profile):
    text = job["title"] + "\n" + job["description"]
    # User-confirmed aliases affect discovery only, never the original source text.
    for alias in profile.get("matching_aliases", []):
        text = re.sub(alias["pattern"], alias["replacement"], text, flags=re.I)
    tracks = []
    for key, rule in profile["tracks"].items():
        if re.search(rule["title"], job["title"], re.I) and all(re.search(rx, text, re.I) for rx in rule.get("stack_all", [])):
            tracks.append(key)
    project_pattern = profile.get("project_employment_pattern")
    if "projects" in profile["tracks"] and "projects" not in tracks and project_pattern and re.search(project_pattern, str(job.get("employment_type", "")), re.I):
        if all(re.search(rx, text, re.I) for rx in profile["tracks"]["projects"]["stack_all"]):
            tracks.append("projects")
    # Keep the evidence; hints never declare eligibility or a completed degree.
    degree = [x.strip() for x in re.split(r"[\n.;]", job["description"]) if re.search(r"bachelor|degree|תואר|השכלה", x, re.I)]
    location = job.get("location", "")
    allowed = {str(c).casefold() for c in profile["eligible_countries"]}
    countries = {str(c).casefold() for c in job.get("countries_stated", [])}
    if job.get("country_stated"):
        countries.add(str(job["country_stated"]).casefold())
    local = bool(countries & allowed) if countries else bool(re.search(profile["location_pattern"], location, re.I))
    if job.get("provider") == "techmap":
        local = False  # A discovery-only city is not country or eligibility evidence.
    return {**job, "tracks": tracks, "location_scope": "configured_geography" if local else "needs_location_check",
            "education_excerpts": degree, "fit_status": "unreviewed"}



def collect_boards(profile, workdir=None):
    validate_profile(profile)
    boards, failures = {}, []
    if profile.get("employer_registry_enabled", False):
        try:
            if workdir is None:
                raise ValueError("Explicit workspace needed to load employer registry")
            for board in load_boards(workdir, profile):
                boards[board["key"]] = board
        except Exception as exc:
            failures.append({"board_key": "employer-registry", "company": "Employer registry", "error": type(exc).__name__ + ": registry unavailable; not checked"})
    if profile.get("techmap_enabled", False):
        for category in profile.get("techmap_categories", TECHMAP_CATEGORIES):
            if category not in TECHMAP_CATEGORIES:
                raise ValueError("Unknown Techmap category")
            key = "techmap::" + category
            boards[key] = {"provider": "techmap", "tenant": category, "region": "", "category": category,
                           "company": "Techmap / " + category, "key": key,
                           "url": f"https://raw.githubusercontent.com/mluggy/techmap/main/jobs/{category}.csv",
                           "priority": 200, "license": "ODbL-1.0", "attribution": "Michael Lugassy"}
    if profile.get("directory_enabled", False):
        try:
            data = json.loads(get(profile["directory_url"]))
            for item in data["companies"]:
                b = board_from(item.get("sourceUrl", ""), item["name"])
                if b:
                    boards.setdefault(b["key"], b)
        except Exception as exc:
            failures.append({"board_key": "directory", "company": "Company directory", "error": type(exc).__name__ + ": directory fetch/schema failed"})
    for name, url in profile.get("extra_boards", {}).items():
        b = board_from(url, name)
        if b:
            boards[b["key"]] = b
        else:
            failures.append({"board_key": "manual:" + name, "company": name, "error": "Unsupported board; use manual source research"})
    return sorted(boards.values(), key=lambda b: (b.get("priority", 100), b["key"])), failures


def history_changes(previous, current, successful):
    ids = {j["id"] for j in current}
    return [{"id": j["id"], "company": j["company"], "title": j["title"],
             "status": "not_listed_in_successful_scan" if j["board_key"] in successful else "not_checked"}
            for j in previous if j["id"] not in ids]


def scan(workdir, network=False, fixtures=None, limit=None):
    profile = load_profile(workdir)  # Validate before any network or output mutation.
    workdir = private_root(workdir)
    now = dt.datetime.now(ZoneInfo(profile["timezone"]))
    fixture_mode = fixtures is not None
    brief = search_brief(profile, now)
    if fixture_mode:
        brief["run_type"] = "fixture"
    found, applied = ({"opportunities": [], "search_runs": []}, {"records": []}) if fixture_mode else read_store(workdir)
    runs = workdir / ("fixture-runs" if fixture_mode else "runs")
    runs.mkdir(exist_ok=True)
    previous_runs = sorted(p for p in runs.iterdir() if p.is_dir() and (p / "meta.json").exists())
    previous = load(previous_runs[-1] / "all_jobs.json", []) if previous_runs else []
    first_seen = {}
    for old in previous_runs:
        for j in load(old / "all_jobs.json", []):
            first_seen.setdefault(j["id"], j.get("first_seen_at", ""))
    jobs, successful, failed, checks = [], [], [], []
    if fixture_mode:
        fixture = load(fixtures)
        boards = [item["board"] for item in fixture["boards"]]
        for item in fixture["boards"]:
            b = item["board"]
            if "error" in item:
                failed.append({"board_key": b["key"], "company": b["company"], "error": item["error"]})
            else:
                jobs.extend(normalize(b, item["jobs"]))
                successful.append(b["key"])
    elif network:
        boards, failed = collect_boards(profile, workdir)
        if limit is not None:
            checks.extend({"board_key": b["key"], "status": "not_checked", "reason": "Explicit board limit"} for b in boards[limit:])
            boards = boards[:limit]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            pending = {executor.submit(fetch, b): b for b in boards}
            for future in concurrent.futures.as_completed(pending):
                b = pending[future]
                try:
                    result = future.result()
                    jobs.extend(result)
                    errors = getattr(result, "errors", [])
                    if errors:
                        failed.append({"board_key": b["key"], "company": b["company"], "error": "Partial result; details or pagination incomplete", "details": errors})
                        checks.append({"board_key": b["key"], "status": "partial", "records": len(result), "errors": errors})
                    else:
                        successful.append(b["key"])
                        checks.append({"board_key": b["key"], "status": "successful_empty" if not result else "successful", "records": len(result)})
                except Exception as exc:
                    # Do not log URLs containing a public careers token.
                    failed.append({"board_key": b["key"], "company": b["company"], "error": type(exc).__name__ + ": fetch/parse failed; board not checked"})
                    checks.append({"board_key": b["key"], "status": "fetch_failed", "records": None})
    else:
        raise ValueError("Pass --network for an authorized search, or --fixtures for an offline test")
    all_jobs = [classify(j, profile) for j in deduplicate_discoveries(jobs)]
    for j in all_jobs:
        j["checked_at"] = now.isoformat()
        j["first_seen_at"] = first_seen.get(j["id"]) or now.isoformat()
        j["new_to_tracker"] = j["id"] not in first_seen
        j["history_check"] = history_decision(j, found, applied)
        j["qualification"] = qualify(j, {}, brief, now, found, applied)
    all_jobs.sort(key=lambda j: j["id"])
    hits = [j for j in all_jobs if set(j["tracks"]) & set(brief["tracks"])]
    run = runs / (now.strftime("%Y%m%dT%H%M%S%f") + "-" + uuid.uuid4().hex[:6])
    run.mkdir()
    save(run / "all_jobs.json", all_jobs)
    save(run / "profile-snapshot.json", profile)
    save(run / "boards.json", boards)
    save(run / "hits.json", hits)
    save(run / "failed.json", failed)
    save(run / "changes.json", history_changes(previous, all_jobs, successful))
    meta = {"schema_version": 2, "id": run.name, "checked_at": now.isoformat(), "timezone": profile["timezone"],
                             "search_brief": brief, "window_start": brief["window_start"], "window_end": brief["window_end"],
                             "requested_minimum": brief["requested_minimum"], "qualified_count": 0,
                             "shortfall": brief["requested_minimum"],
                             "fixture_mode": fixture_mode, "boards_attempted": len(boards), "boards_successful": len(successful),
                             "successful_board_keys": successful, "source_checks": checks, "coverage_limited": limit is not None,
                             "jobs_read": len(all_jobs), "track_matches": len(hits), "failures": len(failed),
                             "meaning": "Public listings read; application routes and candidate suitability require review"}
    save(run / "meta.json", meta)
    if not fixture_mode:
        # Reload before merging so observations cannot overwrite intervening record edits.
        latest, _ = read_store(workdir)
        save_canonical(workdir / "data/jobs.json", merge_discovery(latest, all_jobs, meta))
        record_source_checks(workdir, profile, checks, now.isoformat())
    return run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workdir", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--network", action="store_true")
    mode.add_argument("--fixtures", type=Path)
    parser.add_argument("--limit-boards", type=int)
    args = parser.parse_args()
    if args.limit_boards is not None and args.limit_boards < 1:
        parser.error("--limit-boards must be positive")
    print(scan(args.workdir, args.network, args.fixtures, args.limit_boards))
