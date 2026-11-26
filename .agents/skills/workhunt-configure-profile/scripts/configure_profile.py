"""Map a reviewed evidence ledger into private templates; no CV parser or network."""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE.parent / "workhunt-search/scripts"))
from profile_config import private_root, validate_profile

FACT_FIELDS = {"name", "headline", "identity", "capabilities", "experience", "education", "languages"}
SETTING_FIELDS = {"tracks", "eligible_countries", "location_pattern", "timezone", "language", "limited_experience", "degree_policy", "preferences", "search_brief", "directory_enabled", "directory_url", "employer_registry_enabled", "employer_registry", "employer_overrides", "source_health", "techmap_enabled", "techmap_categories", "extra_boards", "manual_sources", "matching_aliases", "project_employment_pattern"}
OUTPUTS = {"profile.json": "profile.template.json", "profile-evidence.json": "profile-evidence.template.json", "professional-summary.md": "professional-summary.template.md"}


def initialize(workspace):
    root = private_root(workspace)
    for output, template in OUTPUTS.items():
        if (root / output).exists():
            raise ValueError("Existing private profile output must be reviewed, not overwritten: " + output)
    root.mkdir(parents=True, exist_ok=True)
    for output, template in OUTPUTS.items():
        (root / output).write_bytes((PACKAGE / "assets" / template).read_bytes())
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


def map_ledger(ledger):
    profile = json.loads((PACKAGE / "assets/profile.template.json").read_text(encoding="utf-8"))
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


def populate(workspace, ledger):
    """Fill new or untouched private templates; preserve populated candidate/history data."""
    profile, evidence = map_ledger(ledger)
    root = private_root(workspace)
    for name, template in OUTPUTS.items():
        if (root / name).exists() and (root / name).read_bytes() != (PACKAGE / "assets" / template).read_bytes():
            raise ValueError("Existing private profile output requires a reviewed update: " + name)
    root.mkdir(parents=True, exist_ok=True)
    (root / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "profile-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = "# Private professional summary\n\nCandidate: " + (profile["name"] or "Unknown") + "\n\n"
    summary += "Supported capabilities: " + ", ".join(str(c.get("name", "Unspecified")) for c in profile["capabilities"]) + "\n\n"
    summary += "Evidence references: " + ", ".join(profile["evidence_references"]) + "\n\n"
    summary += "Conflicts: " + str(len(evidence.get("conflicts", []))) + "; unknowns: " + str(len(evidence.get("unknowns", []))) + ". See the private evidence ledger.\n\nDraft only; not published or sent.\n"
    (root / "professional-summary.md").write_text(summary, encoding="utf-8")
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--initialize", action="store_true", required=True, help="Create empty private copies; never parse or upload a CV")
    args = parser.parse_args()
    print(initialize(args.workspace))
