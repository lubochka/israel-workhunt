"""Map a reviewed evidence ledger into private templates; no CV parser or network."""
import argparse
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE.parent / "workhunt-search/scripts"))
from profile_config import private_root, private_path, cv_manifest_path, validate_profile

FACT_FIELDS = {"name", "headline", "identity", "capabilities", "experience", "education", "languages"}
SETTING_FIELDS = {"tracks", "eligible_countries", "location_pattern", "timezone", "language", "limited_experience", "degree_policy", "preferences", "work_location_policy", "search_brief", "directory_enabled", "directory_url", "employer_registry_enabled", "employer_registry", "employer_overrides", "source_health_file", "techmap_enabled", "techmap_categories", "extra_boards", "manual_sources", "matching_aliases", "project_employment_pattern"}
OUTPUTS = {"profile.json": "profile.template.json", "profile-evidence.json": "profile-evidence.template.json", "professional-summary.md": "professional-summary.template.md", "cv-manifest.json": "cv-manifest.template.json"}


def template_root(shared=None):
    if shared is None:
        return PACKAGE / "assets"
    from workspace import resolve_workspace
    return resolve_workspace(explicit=shared) / "templates"


def initialize(workspace, shared=None):
    root = private_root(workspace)
    templates = template_root(shared)
    contents = {output: (templates / template).read_bytes() for output, template in OUTPUTS.items()}
    for output, template in OUTPUTS.items():
        if (root / output).exists():
            raise ValueError("Existing private profile output must be reviewed, not overwritten: " + output)
    root.mkdir(parents=True, exist_ok=True)
    for output, template in OUTPUTS.items():
        (root / output).write_bytes(contents[output])
    return root


def non_overlapping_days(intervals):
    """Exact supported dates only; never infer dates from month/year precision."""
    parsed = []
    for start, end in intervals:
        if not isinstance(start, str) or not isinstance(end, str) or len(start) != 10 or len(end) != 10:
            raise ValueError("Exact tenure requires supported ISO calendar dates")
        left, right = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
        if right < left:
            raise ValueError("Employment interval ends before it starts")
        parsed.append((left, right))
    merged = []
    for start, end in sorted(parsed):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return sum((end - start).days for start, end in merged)


def map_ledger(ledger, shared=None):
    profile = json.loads((template_root(shared) / "profile.template.json").read_text(encoding="utf-8"))
    evidence = copy.deepcopy(ledger)
    sources = {s["id"] for s in evidence.get("sources", [])}
    seen = set()
    conflicting = {f for conflict in evidence.get("conflicts", []) if conflict.get("status") != "resolved" for f in conflict.get("fact_ids", [])}
    intervals, interval_ids, excluded = [], [], []
    for fact in evidence.get("facts", []):
        if not fact.get("id") or fact["id"] in seen or fact.get("source_id") not in sources or not fact.get("locator"):
            raise ValueError("Each fact needs a unique ID, known source and locator")
        seen.add(fact["id"])
        if fact.get("kind") not in {"cv_fact", "user_confirmation", "calculation"}:
            raise ValueError("Fact origin must be explicit")
        if fact.get("kind") == "calculation" and (not fact.get("inputs") or not fact.get("method")):
            raise ValueError("Calculated facts need source inputs and a method")
        target = fact.get("target")
        if target not in FACT_FIELDS:
            raise ValueError("CV facts cannot set search preferences: " + str(target))
        if fact["id"] in conflicting or fact.get("conflict_ids"):
            excluded.append(fact["id"])
            continue
        value = copy.deepcopy(fact["value"])
        if target in {"capabilities", "experience", "education", "languages"}:
            if not isinstance(value, dict):
                raise ValueError("Structured fact required for " + target)
            value["evidence_ids"] = [fact["id"]]
            if target == "capabilities":
                value.setdefault("duration_years", None)
            if target == "education":
                value.setdefault("completed", None)
            if target == "languages":
                value.setdefault("proficiency", None)
            profile[target].append(value)
            if target == "experience":
                if value.get("start") and value.get("end") and value.get("date_precision") == "day":
                    intervals.append((value["start"], value["end"]))
                    interval_ids.append(fact["id"])
                else:
                    excluded.append(fact["id"])
        else:
            if profile[target] and profile[target] != value:
                raise ValueError("Conflicting scalar facts must be recorded as a conflict")
            profile[target] = value
        profile["evidence_references"].append(fact["id"])
    for decision in evidence.get("decisions", []):
        if decision.get("target") not in SETTING_FIELDS or decision.get("kind") != "user_confirmation" or decision.get("source_id") not in sources or not decision.get("locator") or not decision.get("evidence"):
            raise ValueError("Search settings require an explicit sourced user confirmation")
        profile[decision["target"]] = copy.deepcopy(decision["value"])
        if decision["target"] == "work_location_policy":
            if not isinstance(profile["work_location_policy"], dict):
                raise ValueError("Work-location policy requires a structured user confirmation")
            profile["work_location_policy"]["provenance"] = {key: copy.deepcopy(decision[key]) for key in ("source_id", "locator", "evidence")}
        if decision["target"] == "search_brief" and isinstance(profile["search_brief"], dict) and "project_stack_policy" in profile["search_brief"]:
            policy = profile["search_brief"]["project_stack_policy"]
            if not isinstance(policy, dict):
                raise ValueError("Project policy requires a structured user confirmation")
            policy["provenance"] = {key: copy.deepcopy(decision[key]) for key in ("source_id", "locator", "evidence")}
    evidence["tenure_calculation"] = {"kind": "calculation", "method": "union of exact half-open date intervals", "input_fact_ids": interval_ids,
                                        "excluded_or_unresolved_fact_ids": excluded, "supported_non_overlapping_days": non_overlapping_days(intervals) if intervals else None}
    profile["configured"] = True
    try:
        validate_profile(profile)
        evidence["configuration_status"] = {"configured": True, "validation_error": None}
    except ValueError as exc:
        profile["configured"] = False
        evidence["configuration_status"] = {"configured": False, "validation_error": str(exc)}
    return profile, evidence


def render_summary(profile, evidence, shared=None):
    """Fill the shared summary contract using supported facts and explicit preferences."""
    template = (template_root(shared) / "professional-summary.template.md").read_text(encoding="utf-8")
    confirmed_tracks = any(d.get("target") == "tracks" and d.get("kind") == "user_confirmation" for d in evidence.get("decisions", []))
    target_role = ", ".join(str(rule.get("label") or key) for key, rule in profile.get("tracks", {}).items()) if confirmed_tracks else ""
    capabilities = "; ".join(str(item.get("name") or "Unnamed supported capability") for item in profile.get("capabilities", []))
    experience = []
    for item in profile.get("experience", []):
        role = item.get("title") or item.get("role") or "Role not stated"
        employer = item.get("employer") or "Employer not stated"
        dates = f"{item.get('start') or 'start unknown'} to {item.get('end') or 'end unknown'}"
        refs = ", ".join(item.get("evidence_ids", []))
        duties = item.get("responsibilities") or []
        duties = "; ".join(str(d) for d in duties) if isinstance(duties, list) else str(duties)
        experience.append(f"- {role} at {employer}; {dates}." + (f" {duties}." if duties else "") + (f" Evidence: {refs}." if refs else ""))
    tenure = evidence.get("tenure_calculation", {})
    days = tenure.get("supported_non_overlapping_days")
    excluded = tenure.get("excluded_or_unresolved_fact_ids", [])
    if days is not None:
        experience.append(f"- Supported exact-date employment union: {days:,} days; overlapping intervals counted once.")
        experience.append("- This is a partial tenure total; unresolved or imprecise intervals are excluded: " + ", ".join(excluded) + "." if excluded else "- This covers only the supported exact-date intervals in the ledger.")
        experience.append("- Employment tenure does not establish years in any individual technology.")
    else:
        experience.append("- Exact employment tenure is unknown; no supported complete date intervals were available.")
    for item in profile.get("education", []):
        qualification = item.get("qualification") or item.get("programme") or item.get("name") or "Education record"
        completed = "completed" if item.get("completed") is True else "not completed" if item.get("completed") is False else "completion unknown"
        experience.append(f"- Education: {qualification}; {completed}. Evidence: " + ", ".join(item.get("evidence_ids", [])) + ".")
    sources = {s["id"]: s for s in evidence.get("sources", [])}
    references = []
    for fact in evidence.get("facts", []):
        source = sources.get(fact.get("source_id"), {})
        location = source.get("path") or source.get("reference") or source.get("id") or "source unknown"
        references.append(f"- {fact['id']}: {location}; {fact['locator']}.")
    unresolved = []
    for conflict in evidence.get("conflicts", []):
        if conflict.get("status") != "resolved":
            unresolved.append("- Unresolved conflict " + str(conflict.get("id", "unidentified")) + ": " + str(conflict.get("evidence") or conflict.get("dependent_claims") or conflict.get("claims") or "See the evidence ledger.").rstrip(".") + ".")
    for unknown in evidence.get("unknowns", []):
        if isinstance(unknown, dict):
            unresolved.append("- " + str(unknown.get("target") or unknown.get("field") or "Unknown fact") + ": " + str(unknown.get("reason") or "Not established").rstrip(".") + ".")
        else:
            unresolved.append("- " + str(unknown))
    if not target_role:
        unresolved.append("- Desired role remains unknown; career titles and the headline do not establish a search preference.")
    if not profile.get("configured"):
        unresolved.append("- Scanning remains unconfigured; missing explicit search settings must be resolved before any scan.")
    values = {
        "candidate_name": profile.get("name") or profile.get("identity", {}).get("name") or "Candidate identity unknown",
        "target_role": target_role or "Unknown; no explicit role preference supplied",
        "technology_or_capability": capabilities or "No supported capability mapped",
        "verified_experience": "\n" + "\n".join(experience),
        "source_reference": "\n" + ("\n".join(references) or "No supported source references"),
        "unresolved_facts": "\n" + ("\n".join(unresolved) or "No unresolved facts recorded; absence is not independent verification."),
    }
    def replace(match):
        if match[1] not in values:
            raise ValueError("Unknown professional-summary template field: " + match[1])
        return str(values[match[1]])
    return re.sub(r"\{\{([a-z_]+)\}\}", replace, template)


def cv_version(path, language=None, roles=None, selection_evidence=None, content_review=None, unresolved=None):
    """Measure an explicitly selected local file; never infer preferences or review."""
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise ValueError("Explicitly selected CV file is missing")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    at = dt.datetime.now(dt.timezone.utc).isoformat()
    if language is not None and (not isinstance(language, str) or not language.strip()):
        raise ValueError("CV language must be supported text or null")
    if roles is not None and (not isinstance(roles, list) or any(not isinstance(role, str) or not role.strip() for role in roles)):
        raise ValueError("CV roles must be an explicit list of supported mappings")
    if (language or roles) and not selection_evidence:
        raise ValueError("CV language/role mapping needs supported selection evidence")
    if content_review and not (content_review.get("status") == "reviewed" and content_review.get("evidence") and content_review.get("sha256") == digest):
        raise ValueError("Content review must cite evidence for the exact measured file")
    unknowns = list(unresolved or [])
    if not language:
        unknowns.append("Language not established")
    if not roles:
        unknowns.append("Role mapping not established; career headline is not a desired role")
    return {"version_id": "cv-" + digest[:16] + "-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"),
            "path": str(path), "sha256": digest, "measured_at": at, "language": language,
            "roles": list(roles or []), "selection_status": "current" if language and roles and selection_evidence else "unresolved",
            "selection_evidence": selection_evidence, "content_review": content_review or {"status": "not_reviewed", "evidence": None},
            "unresolved_facts": unknowns}


def register_cv(workspace, path, **mapping):
    """Append private versions without retiring another version by guesswork."""
    root = private_root(workspace)
    profile = json.loads((root / "profile.json").read_text(encoding="utf-8"))
    manifest_path = cv_manifest_path(root, profile)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"schema_version": 1, "versions": [], "historical_references": []}
    version = cv_version(path, **mapping)
    manifest.setdefault("versions", []).append(version)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return version


def populate(workspace, ledger, selected_cv=None, cv_mapping=None, shared=None):
    """Fill new or untouched private templates; preserve populated candidate/history data."""
    profile, evidence = map_ledger(ledger, shared)
    root = private_root(workspace)
    templates = template_root(shared)
    for name, template in OUTPUTS.items():
        if name == "cv-manifest.json":
            continue  # Previous private CV versions are retained below.
        if (root / name).exists() and (root / name).read_bytes() != (templates / template).read_bytes():
            raise ValueError("Existing private profile output requires a reviewed update: " + name)
    summary = render_summary(profile, evidence, shared)
    manifest_path = cv_manifest_path(root, profile)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else json.loads((templates / "cv-manifest.template.json").read_text(encoding="utf-8"))
    if selected_cv:
        manifest["versions"].append(cv_version(selected_cv, **(cv_mapping or {})))
    root.mkdir(parents=True, exist_ok=True)
    (root / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "profile-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "professional-summary.md").write_text(summary, encoding="utf-8")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--shared-workspace", type=Path, help="Shared release root; resolved without a private profile")
    parser.add_argument("--initialize", action="store_true", required=True, help="Create empty private copies; never parse or upload a CV")
    args = parser.parse_args()
    print(initialize(args.workspace, args.shared_workspace))
