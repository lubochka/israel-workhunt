"""Maintained public employer-board registry; imports never test a board's health."""
import copy
import hashlib
import re
import urllib.parse as up
from pathlib import Path
from records import load, save
from profile_config import private_root, private_path, shared_root

UPSTREAM_REVISION = "7e3a2a8a21c7bea967ddccf6812163ee45adc2f2"
UPSTREAM_URL = f"https://raw.githubusercontent.com/ahiraz/israel-job-search/{UPSTREAM_REVISION}/data/companies.json"
TECHMAP_CATEGORIES = ["admin", "business", "data-science", "design", "devops", "finance", "frontend", "hardware", "hr", "legal", "marketing", "procurement-operations", "product", "project-management", "qa", "sales", "security", "software", "support"]
PROVIDERS = {"greenhouse", "lever", "ashby", "comeet", "smartrecruiters", "recruitee"}


def board_from(url, company):
    if not isinstance(url, str) or not url.strip():
        return None
    p = up.urlsplit(url)
    if p.scheme not in {"http", "https"} or p.username:
        return None
    host, bits = (p.hostname or "").lower(), p.path.strip("/").split("/")
    provider = tenant = region = ""
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io", "boards.eu.greenhouse.io", "job-boards.eu.greenhouse.io"}:
        provider, region = "greenhouse", "eu" if ".eu." in host else "us"
        tenant = up.parse_qs(p.query).get("for", [bits[0]])[0]
    elif host == "jobs.ashbyhq.com":
        provider, tenant = "ashby", bits[0]
    elif host in {"jobs.lever.co", "jobs.eu.lever.co"}:
        provider, tenant, region = "lever", bits[0], "eu" if ".eu." in host else "us"
    elif host in {"www.comeet.com", "comeet.com", "www.comeet.co", "comeet.co"}:
        if len(bits) >= 3 and bits[0] == "jobs":
            provider, tenant = "comeet", bits[2]
        elif len(bits) >= 4 and bits[:3] == ["careers-api", "2.0", "company"]:
            provider, tenant = "comeet", bits[3]
    elif host in {"careers.smartrecruiters.com", "jobs.smartrecruiters.com"}:
        provider, tenant = "smartrecruiters", bits[0]
    elif host == "api.smartrecruiters.com" and len(bits) >= 3 and bits[:2] == ["v1", "companies"]:
        provider, tenant = "smartrecruiters", bits[2]
    elif host.endswith(".recruitee.com") and len(host.split(".")) == 3:
        provider, tenant = "recruitee", host.split(".")[0]
    if not provider or not re.fullmatch(r"[A-Za-z0-9_.-]+", tenant):
        return None
    return {"provider": provider, "tenant": tenant, "region": region, "company": company,
            "url": url, "key": f"{provider}:{region}:{tenant.lower()}"}


def upstream_board(row):
    provider = row.get("provider")
    if provider not in PROVIDERS:
        raise ValueError("Unsupported upstream provider")
    token = str(row.get("token", ""))
    tenant, separator, public_token = token.partition("::")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", tenant) or provider == "comeet" and not separator:
        raise ValueError("Invalid public board identifier")
    parsed = board_from(row.get("careers_url"), row.get("name"))
    region = parsed["region"] if parsed and parsed["provider"] == provider else "us" if provider in {"lever", "greenhouse"} else ""
    urls = {"greenhouse": f"https://job-boards.{'eu.' if region == 'eu' else ''}greenhouse.io/{tenant}",
            "lever": f"https://jobs.{'eu.' if region == 'eu' else ''}lever.co/{tenant}",
            "ashby": f"https://jobs.ashbyhq.com/{tenant}",
            "smartrecruiters": f"https://careers.smartrecruiters.com/{tenant}",
            "recruitee": f"https://{tenant}.recruitee.com/api/feeds/offers.xml",
            "comeet": f"https://www.comeet.co/careers-api/2.0/company/{tenant}/positions?" + up.urlencode({"token": public_token, "details": "true"})}
    return {"key": f"{provider}:{region}:{tenant.lower()}", "provider": provider, "tenant": tenant, "region": region,
            "company": row["name"], "domain": row.get("domain", ""), "url": urls[provider],
            "careers_url": row.get("careers_url", ""), "enabled": True, "priority": 100,
            "health": {"status": "unverified", "checked_at": None, "reason": "Imported source identity only; no runtime request"},
            "upstream_record": copy.deepcopy(row), "license": "MIT",
            "limitations": ["Source import does not establish current board or application availability"] +
                (["Conditional public XML only; JSON Careers Site API token deadline 2027-02-10; no credentials used"] if provider == "recruitee" else [])}


def build_registry(rows, existing=None, snapshot_sha256=None, source_url=UPSTREAM_URL, revision=UPSTREAM_REVISION):
    if not isinstance(rows, list):
        raise ValueError("Upstream employer snapshot must be an array")
    old = copy.deepcopy(existing or {})
    boards = {b["key"]: b for b in old.get("boards", [])}
    seen = set()
    for row in rows:
        new = upstream_board(row)
        key = new["key"]
        if key in seen:
            raise ValueError("Duplicate provider/region/tenant in upstream snapshot: " + key)
        seen.add(key)
        if key in boards:
            # Runtime health and local metadata are never reset by an import.
            previous = boards[key]
            new = {**previous, **new, "priority": previous.get("priority", 100), "enabled": previous.get("enabled", True), "health": previous.get("health", new["health"])}
        new["upstream_presence"] = "present"
        boards[key] = new
    for key, value in boards.items():
        if key not in seen:
            value["upstream_presence"] = "missing_in_latest_snapshot"
            # Upstream disappearance is not evidence that an employer stopped hiring.
    return {**old, "schema_version": 1, "provenance": {"repository": "https://github.com/ahiraz/israel-job-search",
            "source_url": source_url, "revision": revision, "snapshot_sha256": snapshot_sha256,
            "license": "MIT", "attribution": "Copyright (c) 2026 israel-job-search contributors",
            "license_file": "upstream/israel-job-search/LICENSE"}, "boards": sorted(boards.values(), key=lambda b: b["key"])}


def effective_boards(registry, overrides=None, include_disabled=False):
    overrides = overrides or {}
    corrections = overrides.get("boards", {})
    boards = []
    for original in registry.get("boards", []) + overrides.get("additions", []):
        board = {**copy.deepcopy(original), **copy.deepcopy(corrections.get(original["key"], {}))}
        if board["key"] != original["key"]:
            raise ValueError("An override cannot rewrite the stable registry key; add a new board and disable the old one")
        if board.get("provider") not in PROVIDERS or not re.fullmatch(r"[A-Za-z0-9_.-]+", str(board.get("tenant", ""))):
            raise ValueError("Invalid provider/tenant in local override")
        if board["key"] != f"{board['provider']}:{board.get('region', '')}:{board['tenant'].lower()}":
            raise ValueError("Provider/tenant correction requires a new stable board identity")
        if include_disabled or board.get("enabled", True):
            boards.append(board)
    if len({b["key"] for b in boards}) != len(boards):
        raise ValueError("Duplicate effective registry keys")
    return sorted(boards, key=lambda b: (b.get("priority", 100), b["key"]))


def load_boards(workdir, profile, include_disabled=False):
    root = private_root(workdir)
    relative = profile.get("employer_registry", "sources/employer-boards.json")
    registry_file = private_path(root, relative)
    if not registry_file.exists():
        registry_file = (shared_root(workdir) / relative).resolve()
        if not registry_file.is_relative_to(shared_root(workdir)):
            raise ValueError("Shared registry must stay inside the selected release root")
    registry = load(registry_file)
    if not registry:
        raise ValueError("Configured employer registry is missing")
    overrides = load(private_path(root, profile.get("employer_overrides", "sources/employer-overrides.json")), {})
    boards = effective_boards(registry, overrides, include_disabled)
    health = load(private_path(root, profile.get("source_health_file", profile.get("source_health", "sources/source-health.json"))), {}).get("sources", {})
    for board in boards:
        if board["key"] in health:
            board["health"] = health[board["key"]]
    return boards


def record_source_checks(workdir, profile, checks, checked_at):
    """Persist only actual collector observations; retain last success across failures."""
    path = private_path(workdir, profile.get("source_health_file", profile.get("source_health", "sources/source-health.json")))
    data = load(path, {"schema_version": 1, "sources": {}})
    for check in checks:
        status = check["status"]
        if status not in {"not_checked", "fetch_failed", "partial", "successful", "successful_empty"}:
            raise ValueError("Unknown source observation status")
        row = data["sources"].setdefault(check["board_key"], {"status": "unverified", "last_successful_check_at": None})
        row["status"] = status
        row["last_observation"] = {**copy.deepcopy(check), "recorded_at": checked_at}
        if status != "not_checked":
            row["last_attempt_at"] = checked_at
        if status in {"successful", "successful_empty"}:
            row["last_successful_check_at"] = checked_at
            row["last_successful_record_count"] = check["records"]
    save(path, data)


def update_registry(workdir, snapshot, apply=False, source_url=UPSTREAM_URL, revision=UPSTREAM_REVISION):
    import json
    root, snapshot = private_root(workdir), Path(snapshot)
    raw = snapshot.read_bytes()
    previous = load(root / "sources/employer-boards.json", {})
    updated = build_registry(json.loads(raw.decode("utf-8-sig")), previous, hashlib.sha256(raw).hexdigest(), source_url, revision)
    overrides = load(root / "sources/employer-overrides.json", {})
    effective_boards(updated, overrides)  # Validate without modifying local corrections.
    changed = updated != previous
    if apply and changed:
        save(root / "sources/employer-boards.json", updated)
    return {"changed": changed, "applied": bool(apply and changed), "boards": len(updated["boards"]),
            "snapshot_sha256": hashlib.sha256(raw).hexdigest(), "overrides_preserved": True}
