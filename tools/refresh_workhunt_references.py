"""Synchronize only shared English authorities and empty templates; never private state."""
import argparse
import json
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
    ledger = json.loads((root / "templates/profile-evidence.template.json").read_text(encoding="utf-8"))
    if any(ledger.get(key) for key in ("sources", "facts", "conflicts", "unknowns", "decisions")):
        raise ValueError("Shared evidence template must remain empty")
    updates = {}
    authorities = {"context.md": "docs/skills/WORKHUNT_CONTEXT.md", "playbook.md": "JOB_SEARCH_PLAYBOOK.md", "tracking.md": "docs/skills/JOB_TRACKING.md", "opportunity-sources.json": "sources/opportunity-sources.json", "third-party-notices.md": "THIRD_PARTY_NOTICES.md", "upstream-license.txt": "sources/upstream/israel-job-search/LICENSE", "FREELANCE_PROJECT_SOURCES.md": "docs/FREELANCE_PROJECT_SOURCES.md", "REMOTE_JOB_FEEDS.md": "docs/REMOTE_JOB_FEEDS.md"}
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
                    updates[package / "assets" / source.name] = source.read_bytes()
        contents = {p.relative_to(package): p.read_bytes() for p in package.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
        contents.update({p.relative_to(package): data for p, data in updates.items() if p.is_relative_to(package)})
        for provider in PROVIDERS:
            for rel, data in contents.items():
                updates[root / provider / "skills" / package.name / rel] = data
    return updates


def refresh(root=ROOT, check=False):
    changes = [(path, data) for path, data in plan(root).items() if not path.is_file() or path.read_bytes() != data]
    if check and changes:
        raise ValueError("Shared/provider copies need refresh: " + ", ".join(str(p.relative_to(root)) for p, _ in changes[:8]))
    if not check:
        for path, data in changes:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    return {"packages": len(packages(Path(root))), "changed_files": len(changes), "check_only": check}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(refresh(check=args.check)))
