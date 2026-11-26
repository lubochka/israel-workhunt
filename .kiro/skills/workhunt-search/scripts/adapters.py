"""Public discovery adapters. Neither URLs nor feed dates establish application eligibility."""
import csv
import hashlib
import io
import json
import urllib.parse as up
import xml.etree.ElementTree as ET
from records import identity_groups, url_identity


class FetchResult(list):
    """Rows plus completeness: a partial result must never support closure inference."""
    def __init__(self, rows=(), errors=()):
        super().__init__(rows)
        self.errors = list(errors)


def location_text(locations):
    values = []
    for item in locations:
        if isinstance(item, str):
            values.append(item)
        elif isinstance(item, dict):
            values.append(", ".join(str(item.get(k)) for k in ("name", "city", "region", "country") if item.get(k)))
    return " | ".join(dict.fromkeys(x for x in values if x))


def smart_fields(row, plain):
    """Sanitize observed detail fields without discarding safe same-posting facts."""
    issues = []
    def text(value, field, default=""):
        if value is None:
            return default
        if not isinstance(value, str):
            issues.append(field)
            return default
        return value
    ad = row.get("jobAd")
    sections = ad.get("sections") if isinstance(ad, dict) else None
    if not isinstance(sections, dict):
        issues.append("jobAd.sections")
        sections = {}
    safe_sections = {}
    for key, value in sections.items():
        if not isinstance(value, dict):
            issues.append("section:" + str(key))
            continue
        safe_sections[key] = {"title": text(value.get("title"), "section.title", str(key)),
                              "text": text(value.get("text"), "section.text")}
    body = "\n\n".join(plain(value["title"] or key) + "\n" + plain(value["text"]) for key, value in safe_sections.items())
    locations = []
    raw_locations = [row["location"]] if row.get("location") is not None else []
    for key in ("locations", "secondaryLocations"):
        values = row.get(key, [])
        if not isinstance(values, list):
            issues.append(key)
        else:
            raw_locations.extend(values)
    for location in raw_locations:
        if isinstance(location, str):
            locations.append(location)
        elif isinstance(location, dict):
            locations.append({key: text(location[key], "location." + key) for key in ("name", "city", "region", "country") if key in location})
        else:
            issues.append("location")
    def label(key, default=""):
        value = row.get(key)
        if isinstance(value, dict):
            return text(value.get("label"), key + ".label", default)
        return text(value, key, default)
    work_model, employment_type = label("workplaceType", "unknown"), label("typeOfEmployment")
    scalars = {key: text(row.get(key), key) for key in ("name", "postingUrl", "applyUrl", "releasedDate")}
    complete = row.get("_detail_complete") is not False and not issues and all(k in safe_sections for k in ("jobDescription", "qualifications")) and bool(plain(safe_sections.get("jobDescription", {}).get("text", "")))
    return {"text": body, "locations": locations, "work_model": work_model, "employment_type": employment_type,
            "complete": bool(complete), "scalars": scalars, "issues": issues}


def smart_normalize(board, rows, plain):
    result, errors = [], []
    for row in rows:
        ident = str(row.get("id") or row.get("uuid") or "")
        if not ident:
            raise ValueError("SmartRecruiters posting has no exact ID")
        fields = smart_fields(row, plain)
        complete, locations, scalars = fields["complete"], fields["locations"], fields["scalars"]
        if not complete:
            errors.append({"job_id": ident, "error": "Detail unavailable, incomplete or malformed", "fields": fields["issues"]})
        countries = list(dict.fromkeys(x["country"] for x in locations if isinstance(x, dict) and x.get("country")))
        result.append({"id": f"{board['key']}:{ident}", "job_id": ident, "employer_requisition_id": row.get("refNumber"),
                       "provider": "smartrecruiters", "board_key": board["key"], "company": board["company"],
                       "title": scalars["name"], "url": scalars["postingUrl"], "apply_url": scalars["applyUrl"],
                       "description": fields["text"], "description_complete": complete, "description_status": "complete_api_detail" if complete else "detail_failed_or_incomplete",
                       "active": row.get("active") if type(row.get("active")) is bool else None, "locations": locations, "location": location_text(locations),
                       "countries_stated": countries, "country_stated": countries[0] if len(countries) == 1 else "",
                       "work_model_stated": fields["work_model"], "employment_type": fields["employment_type"],
                       "released_at": scalars["releasedDate"], "release_semantics": "Provider release timestamp; original publication not established",
                       "first_published_at": "", "last_published_at": "", "updated_at": "",
                       "application_status": "listing_only", "source": "public_ats", "source_payload": row,
                       "provider_identifiers": {k: row[k] for k in ("id", "uuid", "jobId", "jobAdId", "refNumber") if k in row and isinstance(row[k], (str, int))}})
    return FetchResult(result, errors)


def smart_fetch(board, get, plain):
    base = f"https://api.smartrecruiters.com/v1/companies/{board['tenant']}/postings"
    rows, errors, seen = [], [], set()
    offset, maximum_total = 0, None
    while True:
        try:
            data = json.loads(get(base + "?" + up.urlencode({"limit": 100, "offset": offset})))
            items, total = data["content"], data["totalFound"]
            if not isinstance(items, list) or type(total) is not int or total < 0 or data.get("offset", offset) != offset:
                raise ValueError("Invalid SmartRecruiters pagination shape")
            maximum_total = total if maximum_total is None else max(maximum_total, total)
            ids = [str(item.get("id") or item.get("uuid") or "") for item in items]
            if any(not i for i in ids) or len(set(ids)) != len(ids) or seen.intersection(ids):
                raise ValueError("SmartRecruiters pagination repeated or missing posting IDs")
            if not items and len(seen) < maximum_total:
                raise ValueError("SmartRecruiters pagination stopped before totalFound")
            for item, ident in zip(items, ids):
                seen.add(ident)
                available = item
                try:
                    detail = json.loads(get(base + "/" + up.quote(ident, safe="")))
                    if not isinstance(detail, dict) or str(detail.get("id") or detail.get("uuid") or "") != ident:
                        raise ValueError("SmartRecruiters detail identity mismatch")
                    available = {**item, **detail}
                    rows.append({**item, **detail, "_detail_complete": True})
                except Exception as exc:
                    rows.append({**available, "_detail_complete": False})
                    errors.append({"job_id": ident, "error": type(exc).__name__ + ": detail unavailable or incomplete"})
            offset += len(items)
            if len(seen) >= maximum_total:
                break
        except Exception as exc:
            errors.append({"error": type(exc).__name__ + ": list pagination incomplete", "offset": offset})
            break
    normalized = smart_normalize(board, rows, plain)
    return FetchResult(normalized, errors + normalized.errors)


def techmap_parse(board, text):
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff"), newline=""))
    required = {"company", "title", "city", "url", "updated"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise ValueError("Techmap CSV schema missing required discovery columns")
    rows = []
    for row in reader:
        if None in row or any(row.get(k) is None for k in required):
            raise ValueError("Malformed Techmap CSV row")
        identity = url_identity(row["url"])
        if not identity or not row["title"] or not row["company"]:
            raise ValueError("Techmap discovery row has no exact public listing identity")
        ident = hashlib.sha256(identity.encode()).hexdigest()[:24]
        rows.append({"id": "techmap:" + ident, "job_id": "", "company": row["company"], "title": row["title"],
                     "provider": "techmap", "board_key": board["key"], "url": row["url"], "apply_url": "", "description": "",
                     "description_complete": False, "description_status": "discovery_only", "location": row["city"],
                     "location_scope": "needs_location_check", "country_stated": "", "work_model_stated": "unknown",
                     "source": "techmap_csv", "source_updated_at": row["updated"], "source_updated_precision": "date" if len(row["updated"]) == 10 else "unresolved",
                     "first_published_at": "", "last_published_at": "", "updated_at": "", "application_status": "listing_only",
                     "discovery_categories": [board["category"]], "source_payload": row,
                     "provenance": {"source_url": board["url"], "category": board["category"], "attribution": "Michael Lugassy / Techmap",
                                    "repository": "https://github.com/mluggy/techmap", "license": "ODbL-1.0",
                                    "license_url": "https://opendatacommons.org/licenses/odbl/1-0/"}})
    return rows


def recruitee_parse(board, text, plain):
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ValueError("XML DTD/entities are not accepted")
    root = ET.fromstring(text)
    for node in root.iter():
        node.tag = node.tag.split("}")[-1]
    if root.tag != "jobs":
        raise ValueError("Unverified Recruitee feed: expected jobs XML root")
    rows = []
    for node in root.findall("job"):
        def value(key):
            element = node.find(key)
            return "" if element is None else "".join(element.itertext()).strip()
        ident, title, url = value("reference"), value("title"), value("url")
        description = plain(value("description_requirements"))
        if not ident or not title or not url_identity(url) or not description:
            raise ValueError("Incomplete Recruitee feed record; cannot establish full board coverage")
        locations = [{child.tag: (child.text or "").strip() for child in location if child.tag != "translations"}
                     for location in node.findall("./locations/location")]
        if not locations:
            locations = [{key: value(key) for key in ("city", "country", "state") if value(key)}]
        countries = list(dict.fromkeys(x["country"] for x in locations if x.get("country")))
        modes = [name for name in ("hybrid", "on_site", "remote") if value(name).lower() == "true"]
        rows.append({"id": f"{board['key']}:{ident}", "job_id": ident, "board_key": board["key"], "provider": "recruitee",
                     "company": value("company") or board["company"], "title": title, "url": url, "apply_url": value("apply_url"),
                     "description": description, "description_complete": True, "description_status": "complete_xml_description_requirements",
                     "location": location_text(locations), "locations": locations, "countries_stated": countries,
                     "country_stated": countries[0] if len(countries) == 1 else "", "secondary_locations_status": "observed" if node.find("locations") is not None else "unknown",
                     "work_model_stated": " / ".join(modes) or "unknown", "employment_type": value("contract_type"),
                     "first_published_at": "", "last_published_at": "", "updated_at": "", "source_updated_at": value("updated"),
                     "feed_added_at": value("posted"), "feed_added_semantics": "Added to this feed, not proven original publication",
                     "application_status": "listing_only", "source": "public_xml", "source_payload": ET.tostring(node, encoding="unicode"),
                     "source_limits": ["Conditional public XML; anonymous JSON API not used", "Source fields do not establish candidate application eligibility"],
                     "json_auth_transition_at": "2027-02-10"})
    return rows


def deduplicate_discoveries(jobs):
    def unique(values):
        return list({json.dumps(value, sort_keys=True, ensure_ascii=False): value for value in values}.values())

    def observation(job):
        keys = ("id", "url", "board_key", "source", "provenance", "source_payload", "first_published_at", "last_published_at", "updated_at", "source_updated_at", "source_updated_precision", "released_at", "feed_added_at")
        return {key: job[key] for key in keys if key in job}

    result = []
    for group in identity_groups(jobs):
        previous = group[0]
        for job in group[1:]:
            preferred, secondary = (job, previous) if job.get("description") and not previous.get("description") else (previous, job)
            merged = dict(preferred)
            merged["source_aliases"] = unique(preferred.get("source_aliases", []) + secondary.get("source_aliases", []) + [{"id": secondary["id"], "url": secondary.get("url", "")}])
            merged["discovery_categories"] = list(dict.fromkeys(previous.get("discovery_categories", []) + job.get("discovery_categories", [])))
            merged["discovery_sources"] = unique(previous.get("discovery_sources", []) + job.get("discovery_sources", []) + [observation(previous), observation(job)])
            previous = merged
        result.append(previous)
    return result
