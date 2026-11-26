"""Install sixteen Workhunt packages into explicitly selected discovery roots.

Copies are content-verified. Existing unrelated files/configuration are never modified.
An owned file changed outside this installer causes a conflict, not an overwrite.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

PROJECT = Path(__file__).resolve().parent.parent
SOURCES = {p.name: p for base in ("docs/skills", "skills") for p in (PROJECT / base).glob("workhunt-*") if (p / "SKILL.md").is_file()}
NAMES = tuple(sorted(SOURCES))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root):
    return {str(p.relative_to(root)).replace("\\", "/"): digest(p) for p in root.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def install(root, check=False):
    manifest_path = root / ".workhunt-install.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"files": {}}
    planned = {}
    for name in NAMES:
        source = SOURCES[name]
        if not (source / "SKILL.md").is_file():
            raise ValueError(f"Missing canonical skill {source}")
        for rel, sha in inventory(source).items():
            key = name + "/" + rel
            dest = root / key
            if dest.exists():
                actual = digest(dest)
                if actual != sha and actual != manifest.get("files", {}).get(key):
                    raise ValueError(f"Existing unowned or locally modified file: {dest}")
            elif check:
                raise ValueError(f"Missing installed file: {dest}")
            if check and digest(dest) != sha:
                raise ValueError(f"Installed content differs: {dest}")
            planned[key] = (source / rel, dest, sha)
    if not check:
        for source, dest, sha in planned.values():
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists() or digest(dest) != sha:
                shutil.copy2(source, dest)
        root.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps({"source": "Workhunt maintained packages", "skills": NAMES,
                                            "files": {k: v[2] for k, v in planned.items()}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for _, dest, sha in planned.values():
        if digest(dest) != sha:
            raise ValueError(f"Readback mismatch: {dest}")
    return {"root": str(root), "skills": list(NAMES), "verified_files": len(planned), "check_only": check}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True, help="Explicit selected home or isolated test directory; no implicit personal installation")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    home = args.home.resolve()
    roots = [home / ".agents" / "skills", home / ".claude" / "skills", home / ".kiro" / "skills", home / ".gemini" / "config" / "skills"]
    for root in roots:
        print(json.dumps(install(root, args.check), ensure_ascii=False))
