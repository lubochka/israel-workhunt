"""Package and verify 17 Workhunt skills; preserve modified or unowned installations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.parse

PROJECT = Path(__file__).resolve().parent.parent
ENTRY_NAMES = ("workhunt-search", "workhunt-cv", "workhunt-apply", "workhunt-configure-profile")
LINK = re.compile(r"\]\(([^)]+)\)")
RESOLVER = (PROJECT / "skills/workhunt-search/scripts/workspace.py").read_text(encoding="utf-8")


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def inventory(root):
    return {p.relative_to(root).as_posix(): digest_bytes(p.read_bytes()) for p in root.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def canonical_sources(project):
    values = {name: project / "skills" / name for name in ENTRY_NAMES}
    values.update({p.name: p for p in (project / "docs/skills").glob("workhunt-*") if (p / "SKILL.md").is_file()})
    if len(values) != 17:
        raise ValueError("Expected 4 runtime and 13 modular skills; review the source manifest")
    return values


def package(project=PROJECT, workspace=None):
    project = Path(project).resolve()
    workspace = Path(workspace).resolve() if workspace else None
    sources = canonical_sources(project)
    planned, originals = {}, {}
    for name, source in sources.items():
        for file in source.rglob("*"):
            if not file.is_file() or "__pycache__" in file.parts or file.suffix == ".pyc" or file.name == "workspace.local.json":
                continue
            key = name + "/" + file.relative_to(source).as_posix()
            originals[key] = file
            data = file.read_bytes()
            if file.suffix == ".md":
                text = data.decode("utf-8-sig")
                def rewrite(match):
                    target = match[1].strip().strip("<>")
                    if "://" in target or target.startswith("#") or target == "URL" and "/assets/" in key:
                        return match[0]
                    raw, separator, fragment = target.partition("#")
                    resolved = (file.parent / urllib.parse.unquote(raw)).resolve()
                    mapped = None
                    for other, other_root in sources.items():
                        if resolved.is_relative_to(other_root.resolve()):
                            mapped = other + "/" + resolved.relative_to(other_root.resolve()).as_posix()
                            break
                    if mapped is None:
                        if not resolved.is_relative_to(project) or not resolved.is_file():
                            raise ValueError("Unresolved canonical reference: " + str(file) + " -> " + target)
                        relative = resolved.relative_to(project).as_posix()
                        # Shared workspace evidence stays local. This complete packaged pointer
                        # resolves via the workspace script instead of a broken home-relative link.
                        mapped = name + "/references/workspace/" + relative + ".md"
                        pointer = "# Workspace reference\n\nResolve the workspace with this skill's `scripts/resolve_workspace.py` (explicit --workspace, current checkout, then configured fallback). Read `" + relative + "` under that workspace. This pointer packages no CV, contact details or evolving private records.\n"
                        planned[mapped] = pointer.encode("utf-8")
                    relative_link = os.path.relpath(mapped, str(Path(key).parent)).replace("\\", "/")
                    return "](" + urllib.parse.quote(relative_link, safe="/:") + ("#" + fragment if separator else "") + ")"
                text = LINK.sub(rewrite, text)
                if file.name == "SKILL.md":
                    text += "\n## Workspace resolution\n\nRun this skill's `scripts/resolve_workspace.py [--workspace PATH]` when the workspace is uncertain. Precedence is explicit path, current checkout, then private `workspace.local.json` fallback; `workspace.json` is an unbound portable descriptor. Shared references under `references/workspace/` point to exact files in that resolved workspace; private records and CVs are never bundled. Keep automatic skill selection enabled.\n"
                data = text.encode("utf-8")
            planned[key] = data
        planned[name + "/scripts/resolve_workspace.py"] = RESOLVER.encode("utf-8")
        planned[name + "/workspace.json"] = (json.dumps({"workspace": None, "private_root": ".workhunt", "resolution": "explicit > cwd ancestors > private local config"}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    validate_references(planned)
    return planned, originals, sources


def validate_references(files):
    for key, data in files.items():
        if not key.endswith(".md"):
            continue
        for target in LINK.findall(data.decode("utf-8")):
            target = target.strip().strip("<>")
            if "://" in target or target.startswith("#") or target == "URL" and "/assets/" in key:
                continue
            path = urllib.parse.unquote(target.partition("#")[0])
            normalized = os.path.normpath(str(Path(key).parent / path)).replace("\\", "/")
            if normalized not in files:
                raise ValueError("Missing packaged reference: " + key + " -> " + target)


def tracked_version(path, project):
    try:
        relative = path.resolve().relative_to(project.resolve()).as_posix()
    except ValueError:
        return None
    result = subprocess.run(["git", "show", "HEAD:" + relative], cwd=project, capture_output=True)
    return result.stdout if result.returncode == 0 else None


def plan_install(root, files, originals, project, check=False, adopt_project=False):
    root = Path(root).resolve()
    manifest_path = root / ".workhunt-install.json"
    manifest = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {"files": {}}
    for key, data in files.items():
        destination = root / key
        if destination.is_symlink() or not destination.resolve().is_relative_to(root):
            raise ValueError("Unsafe installed path: " + str(destination))
        if not destination.exists():
            if check:
                raise ValueError("Missing installed file: " + str(destination))
            continue
        actual = destination.read_bytes()
        if actual == data:
            continue
        if check:
            raise ValueError("Installed content differs: " + str(destination))
        owned = digest_bytes(actual) == manifest.get("files", {}).get(key)
        original_same = key in originals and actual == originals[key].read_bytes()
        tracked_same = adopt_project and actual == tracked_version(destination, project)
        if not (owned or original_same or tracked_same):
            raise ValueError("Existing unowned or locally modified file: " + str(destination))
    return root, manifest_path


def install(root, check=False, project=PROJECT, workspace=None, adopt_project=False):
    files, originals, sources = package(project, workspace)
    root, manifest_path = plan_install(root, files, originals, Path(project), check, adopt_project)
    bindings = {name + "/workspace.local.json": (json.dumps({"workspace": str(Path(workspace).resolve())}, indent=2) + "\n").encode("utf-8") for name in sources} if workspace else {}
    for key, data in bindings.items():
        dest = root / key
        if dest.exists() and dest.read_bytes() != data:
            raise ValueError("Existing private workspace binding differs: " + str(dest))
        if check and not dest.exists():
            raise ValueError("Missing private workspace binding: " + str(dest))
    if not check:
        for key, data in {**files, **bindings}.items():
            destination = root / key
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists() or destination.read_bytes() != data:
                destination.write_bytes(data)
        manifest_path.write_bytes((json.dumps({"schema_version": 2, "source": "canonical shared release packages", "skills": sorted(sources),
                                              "files": {key: digest_bytes(data) for key, data in files.items()}}, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    for key, data in files.items():
        if (root / key).read_bytes() != data:
            raise ValueError("Readback mismatch: " + str(root / key))
    return {"root": str(root), "skills": len(sources), "verified_files": len(files), "references_verified": True, "check_only": check}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--home", type=Path, help="Explicit personal/temp-home destination; never implicitly writes home")
    scope.add_argument("--project", type=Path, default=None, help="Project discovery roots (default: this checkout)")
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    destination = (args.home or args.project or PROJECT).resolve()
    hosts = [".agents", ".claude", ".kiro"] + ([".gemini/config"] if args.home else [])
    roots = [destination / host / "skills" for host in hosts]
    files, originals, _ = package(PROJECT)
    # Preflight every destination before applying the first one.
    for root in roots:
        plan_install(root, files, originals, PROJECT, args.check, not args.home)
    if args.workspace:
        for root in roots:
            for name in canonical_sources(PROJECT):
                path = root / name / "workspace.local.json"
                expected = (json.dumps({"workspace": str(args.workspace.resolve())}, indent=2) + "\n").encode("utf-8")
                if path.exists() and path.read_bytes() != expected:
                    raise ValueError("Existing private workspace binding differs: " + str(path))
                if args.check and not path.exists():
                    raise ValueError("Missing private workspace binding: " + str(path))
    for root in roots:
        print(json.dumps(install(root, args.check, PROJECT, args.workspace, not args.home)))


if __name__ == "__main__":
    main()
