"""Private profile boundary and conservative pre-network configuration validation."""
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SETUP = "Configure .workhunt/profile.json using workhunt-configure-profile before scanning"


def private_root(workspace):
    """Accept a project directory or its explicit private directory."""
    root = Path(workspace).resolve()
    return root if root.name == ".workhunt" else root / ".workhunt"


def private_path(workspace, relative):
    root = private_root(workspace)
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Private record paths must stay inside .workhunt")
    return target


def shared_root(workspace):
    """Resolve public assets without requiring private profile configuration."""
    from workspace import resolve_workspace
    root = Path(workspace).resolve()
    try:
        return resolve_workspace(cwd=root, config=private_root(root) / "workspace.local.json")
    except ValueError:
        # Runtime source location is a portable fallback in an unpacked release.
        return resolve_workspace(cwd=Path(__file__).resolve().parent)


def safe_output(workspace, path, extra_protected=()):
    """Preflight a private artifact destination without overwriting canonical inputs."""
    root = private_root(workspace)
    target = private_path(root, path)
    protected = {root / name for name in ("profile.json", "profile-evidence.json", "professional-summary.md", "cv-manifest.json", "workspace.local.json", "data/jobs.json", "data/applied_jobs.json", "reviews.json", "applications.json", "manual-opportunities.json", "sources/employer-boards.json", "sources/employer-overrides.json", "sources/source-health.json")}
    profile_file = root / "profile.json"
    if profile_file.is_file():
        profile = json.loads(profile_file.read_text(encoding="utf-8-sig"))
        for field in ("cv_manifest", "employer_registry", "employer_overrides", "source_health_file", "source_health"):
            if profile.get(field):
                protected.add(private_path(root, profile[field]))
    protected.update(Path(p).resolve() for p in extra_protected)
    if target in {p.resolve() for p in protected}:
        raise ValueError("Artifact output cannot overwrite canonical records or configuration")
    return target


def cv_manifest_path(workspace, profile):
    """Validate a custom private manifest without allowing collisions with other inputs."""
    root = private_root(workspace)
    target = private_path(root, profile.get("cv_manifest", "cv-manifest.json"))
    forbidden = {root / name for name in ("profile.json", "profile-evidence.json", "professional-summary.md", "workspace.local.json", "data/jobs.json", "data/applied_jobs.json", "reviews.json", "applications.json", "manual-opportunities.json", "sources/employer-boards.json", "sources/employer-overrides.json", "sources/source-health.json")}
    for field in ("employer_registry", "employer_overrides", "source_health_file", "source_health"):
        if profile.get(field):
            forbidden.add(private_path(root, profile[field]))
    if target in {p.resolve() for p in forbidden}:
        raise ValueError("CV manifest cannot overwrite canonical/configuration or legacy inputs")
    if target.exists():
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("versions"), list) or not isinstance(data.get("historical_references", []), list) or any(not isinstance(row, dict) for row in data["versions"]):
            raise ValueError("Existing CV manifest has an invalid schema")
    return target


def restricted_pattern(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{SETUP}: {field} must be a nonempty restrictive pattern")
    try:
        pattern = re.compile(value, re.I)
    except re.error as exc:
        raise ValueError(f"{SETUP}: {field} is not a valid pattern") from exc
    # Nullable patterns match every input. Also reject broad nonempty wildcards,
    # boundary-only patterns and alternatives that match unrelated probe strings.
    probes = ["", "unrelated placeholder", "123456789", "!@#$%", "zqxv", " "]
    if pattern.search("") or all(pattern.search(p) for p in probes[1:]) or all(pattern.search(p) for p in ["unrelated placeholder", "123456789", "zqxv"]):
        raise ValueError(f"{SETUP}: {field} must not match every or arbitrary input")
    return pattern


def validate_profile(profile):
    if not isinstance(profile, dict) or profile.get("configured") is not True:
        raise ValueError(f"{SETUP}: configured must be true after evidence and preferences are reviewed")
    from work_eligibility import policy_for, policy_gaps
    gaps = policy_gaps(policy_for(profile))
    if gaps:
        raise ValueError(f"{SETUP}: " + "; ".join(gaps))
    tracks = profile.get("tracks")
    if not isinstance(tracks, dict) or not tracks:
        raise ValueError(f"{SETUP}: at least one explicit role track is required")
    for name, rule in tracks.items():
        if not isinstance(rule, dict) or not isinstance(rule.get("label"), str) or not rule["label"].strip():
            raise ValueError(f"{SETUP}: track {name} needs a label")
        restricted_pattern(rule.get("title"), f"tracks.{name}.title")
        patterns = rule.get("stack_all")
        if not isinstance(patterns, list) or not patterns:
            raise ValueError(f"{SETUP}: tracks.{name}.stack_all needs explicit capability patterns")
        for index, pattern in enumerate(patterns):
            restricted_pattern(pattern, f"tracks.{name}.stack_all[{index}]")
    restricted_pattern(profile.get("location_pattern"), "location_pattern")
    countries = profile.get("eligible_countries")
    if not isinstance(countries, list) or not countries or any(not isinstance(c, str) or not c.strip() for c in countries):
        raise ValueError(f"{SETUP}: eligible_countries needs explicit country identifiers")
    try:
        if not isinstance(profile.get("timezone"), str) or not profile["timezone"]:
            raise ValueError()
        ZoneInfo(profile["timezone"])
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError(f"{SETUP}: timezone must be an available IANA time zone") from exc
    if not isinstance(profile.get("language"), str) or not profile["language"].strip():
        raise ValueError(f"{SETUP}: reporting language must be explicit")
    brief = profile.get("search_brief") or {}
    required = brief.get("required_stack")
    if not isinstance(required, list) or not required or any(not isinstance(s, str) or not s.strip() for s in required):
        raise ValueError(f"{SETUP}: search_brief.required_stack needs explicit capability keys")
    selected = brief.get("tracks", list(tracks))
    if not isinstance(selected, list) or not selected or any(not isinstance(t, str) for t in selected):
        raise ValueError(f"{SETUP}: search_brief.tracks must select at least one track")
    if set(selected) - set(tracks):
        raise ValueError(f"{SETUP}: search_brief references an unknown track")
    project_policy = brief.get("project_stack_policy")
    if project_policy is not None and not isinstance(project_policy, dict):
        raise ValueError(f"{SETUP}: project_stack_policy must be an object")
    project_policy = project_policy or {}
    generic = "configured" in project_policy or "alternatives" in project_policy
    if "configured" in project_policy and type(project_policy["configured"]) is not bool:
        raise ValueError(f"{SETUP}: project_stack_policy.configured must be a boolean")
    enabled = project_policy.get("configured") is True if generic else project_policy.get("angular_frontend_without_dotnet") is True
    if enabled:
        from opportunity_types import project_alternatives
        alternatives = project_alternatives(project_policy)
        if not alternatives:
            raise ValueError(f"{SETUP}: enabled project_stack_policy needs valid alternatives, capability keys and restrictive discovery_patterns")
        for alternative in alternatives:
            for key, pattern in alternative["discovery_patterns"].items():
                restricted_pattern(pattern, f"project_stack_policy.{alternative['id']}.discovery_patterns.{key}")
    for name in ("directory_enabled", "employer_registry_enabled", "techmap_enabled"):
        if name in profile and type(profile[name]) is not bool:
            raise ValueError(f"{SETUP}: {name} must be a boolean")
    if profile.get("directory_enabled") and not profile.get("directory_url"):
        raise ValueError(f"{SETUP}: an enabled directory needs an explicit URL")
    for name in ("employer_registry", "employer_overrides", "source_health_file", "source_health", "cv_manifest"):
        if name in profile:
            value = profile[name]
            if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
                raise ValueError(f"{SETUP}: {name} must be a relative private path")
    for alias in profile.get("matching_aliases", []):
        restricted_pattern(alias.get("pattern"), "matching_aliases.pattern")
        if not isinstance(alias.get("replacement"), str):
            raise ValueError(f"{SETUP}: alias replacement must be text")
    if profile.get("project_employment_pattern"):
        restricted_pattern(profile["project_employment_pattern"], "project_employment_pattern")
    return profile


def load_profile(workspace):
    path = private_root(workspace) / "profile.json"
    if not path.is_file():
        raise ValueError(f"{SETUP}: private profile is missing")
    return validate_profile(json.loads(path.read_text(encoding="utf-8-sig")))
