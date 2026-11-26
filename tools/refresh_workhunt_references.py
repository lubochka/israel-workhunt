"""Synchronize only shared English authorities and empty templates; never private state."""
import argparse
import json
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVIDERS = (".agents", ".claude", ".kiro")


def packages(root=ROOT):
    return sorted([p for base in ("docs/skills", "skills") for p in (root / base).glob("workhunt-*") if (p / "SKILL.md").is_file()])


def plan(root=ROOT):
    root = Path(root)
    template = json.loads((root / "templates/profile.template.json").read_text(encoding="utf-8"))
    if template.get("configured") is not False or any(template.get(k) for k in ("name", "headline", "identity", "capabilities", "experience", "education", "languages", "tracks", "eligible_countries", "location_pattern")):
        raise ValueError("Shared profile template must remain empty and unconfigured")
    empty_location_policy = {"base_country": None, "work_path": None, "exclude_required_foreign_conditions": [], "unknown_eligibility": None, "candidate_legal_status": "unknown", "provenance": {}}
    if template.get("work_location_policy") != empty_location_policy:
        raise ValueError("Shared work-location policy must remain empty and unconfigured")
    ledger = json.loads((root / "templates/profile-evidence.template.json").read_text(encoding="utf-8"))
    if any(ledger.get(key) for key in ("sources", "facts", "conflicts", "unknowns", "decisions")):
        raise ValueError("Shared evidence template must remain empty")
    manifest = json.loads((root / "templates/cv-manifest.template.json").read_text(encoding="utf-8"))
    if manifest.get("versions") or manifest.get("historical_references"):
        raise ValueError("Shared CV manifest template must remain empty")
    updates = {}
    authorities = {"MANUAL_DISCOVERY.md": "sources/MANUAL_DISCOVERY.md", "manual-discovery.json": "sources/manual-discovery.json", "context.md": "docs/skills/WORKHUNT_CONTEXT.md", "playbook.md": "JOB_SEARCH_PLAYBOOK.md", "tracking.md": "docs/skills/JOB_TRACKING.md", "opportunity-sources.json": "sources/opportunity-sources.json", "third-party-notices.md": "THIRD_PARTY_NOTICES.md", "upstream-license.txt": "sources/upstream/israel-job-search/LICENSE", "FREELANCE_PROJECT_SOURCES.md": "docs/FREELANCE_PROJECT_SOURCES.md", "REMOTE_JOB_FEEDS.md": "docs/REMOTE_JOB_FEEDS.md"}
    for package in packages(root):
        for dest, source in authorities.items():
            text = (root / source).read_text(encoding="utf-8")
            if dest == "context.md":
                text = text.replace("[profile setup](../../skills/workhunt-configure-profile/SKILL.md)", "the `workhunt-configure-profile` skill")
                text = text.replace("(../../JOB_SEARCH_PLAYBOOK.md)", "(playbook.md)").replace("(JOB_TRACKING.md)", "(tracking.md)")
            elif dest == "third-party-notices.md":
                text = text.replace("(sources/upstream/israel-job-search/LICENSE)", "(upstream-license.txt)")
            elif dest == "opportunity-sources.json":
                catalog = json.loads(text)
                for item in catalog["sources"]:
                    if item.get("guide"):
                        item["guide"] = Path(item["guide"]).name
                text = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
            elif dest in {"FREELANCE_PROJECT_SOURCES.md", "REMOTE_JOB_FEEDS.md"}:
                text = text.replace("(../sources/opportunity-sources.json)", "(opportunity-sources.json)")
            updates[package / "references" / dest] = text.encode("utf-8")
        if package.name == "workhunt-search":
            updates[package / "assets/profile.example.json"] = (root / "templates/profile.template.json").read_bytes()
        if package.name == "workhunt-configure-profile":
            for source in (root / "templates").iterdir():
                if source.is_file():
                    data = source.read_bytes()
                    if source.name == "search-request.template.md":
                        data = data.replace(b"(../workhunt_prompt.md)", b"(../../../workhunt_prompt.md)")
                    updates[package / "assets" / source.name] = data
    return updates


def refresh(root=ROOT, check=False):
    import install_workhunt_skills as installer
    root = Path(root).resolve()
    updates = plan(root)
    changes = [(path, data) for path, data in updates.items() if not path.is_file() or path.read_bytes() != data]
    if check and changes:
        raise ValueError("Shared/provider copies need refresh: " + ", ".join(str(p.relative_to(root)) for p, _ in changes[:8]))
    files, originals, _ = installer.package(root, overlays=updates)
    roots = [root / host / "skills" for host in PROVIDERS]
    for path, _ in changes:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Unsafe shared reference destination")
    for destination in roots:
        installer.plan_install(destination, files, originals, root, check, adopt_project=True)
    if not check:
        for path, data in changes:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    for destination in roots:
        installer.install(destination, check, Path(root), adopt_project=True)
    return {"packages": len(packages(Path(root))), "changed_files": len(changes), "check_only": check}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(refresh(check=args.check)))
