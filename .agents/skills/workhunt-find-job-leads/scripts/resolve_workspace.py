"""Resolve shared release assets independently of any candidate profile."""
import argparse
import json
from pathlib import Path


def is_release(path):
    return (path / "templates/profile.template.json").is_file() and (path / "docs/skills/WORKHUNT_CONTEXT.md").is_file()


def resolve_workspace(explicit=None, cwd=None, config=None):
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if not is_release(candidate):
            raise ValueError("Explicit shared workspace lacks templates and shared context")
        return candidate
    current = Path(cwd or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if is_release(candidate):
            return candidate
    descriptor = Path(config) if config else Path(__file__).resolve().parents[1] / "workspace.local.json"
    if descriptor.is_file():
        saved = json.loads(descriptor.read_text(encoding="utf-8"))
        if saved.get("workspace"):
            candidate = Path(saved["workspace"]).expanduser().resolve()
            if is_release(candidate):
                return candidate
    raise ValueError("Shared workspace unavailable; supply --workspace explicitly")


def resolve_roots(explicit=None, private=None, cwd=None, config=None):
    shared = resolve_workspace(explicit, cwd, config)
    candidate = Path(private).expanduser().resolve() if private else shared / ".workhunt"
    private_root = candidate if candidate.name == ".workhunt" else candidate / ".workhunt"
    return {"shared_root": str(shared), "private_root": str(private_root)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace")
    parser.add_argument("--private-workspace")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    roots = resolve_roots(args.workspace, args.private_workspace)
    print(json.dumps(roots) if args.json else roots["shared_root"])
