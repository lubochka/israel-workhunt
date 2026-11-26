"""Export a reviewed Git inventory without private files or repository history."""
import argparse
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_PARTS = {".git", ".workhunt", "__pycache__", ".venv", "tmp", "output", "validation", "data", "runs", "fixture-runs", "outcomes", "reports", "logs"}
FORBIDDEN_NAMES = {"profile.json", "profile-evidence.json", "professional-summary.md", "cv-manifest.json", "applications.json", "reviews.json", "manual-opportunities.json", ".env", "workspace.local.json", "source-health.json", "employer-overrides.json", "legacy-collector-5f723c0.json", "generate_legacy_brief_fixture.py", "workhunt_prompt.md"}
# Only this reviewed, parameterized public variant may use the otherwise private prompt name.
PUBLIC_PROMPT_SHA256 = "81406ce812e0414d75e26a28be8a66cba416fd5ca23832bb1c93f66475ef923f"
PUBLIC_PROMPT_MARKER = b"<!-- Workhunt public prompt: unfilled candidate-configured workflow; completed requests stay private. -->"
FORBIDDEN_SUFFIXES = {".pdf", ".docx", ".doc", ".pem", ".key", ".pyc", ".pyo"}


def inventory(root=ROOT):
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True)
    paths = [Path(p.decode("utf-8")) for p in result.stdout.split(b"\0") if p]
    if not paths:
        raise ValueError("Stage the reviewed release inventory before export")
    for rel in paths:
        path = root / rel
        public_prompt = rel.as_posix() == "workhunt_prompt.md"
        if rel.is_absolute() or ".." in rel.parts or set(rel.parts) & FORBIDDEN_PARTS or (rel.name in FORBIDDEN_NAMES and not public_prompt) or rel.suffix.lower() in FORBIDDEN_SUFFIXES or rel.name.startswith((".env.", "packet-evidence", "packet-authorization", "submission-event", "draft-request", "local-draft", "coverage-observation", "outcome-events", "source-activity")) or rel.suffix.lower() == ".log":
            raise ValueError("Private or unsupported export entry: " + str(rel))
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Export accepts ordinary files inside the release root only: " + str(rel))
        if public_prompt:
            data = path.read_bytes()
            if PUBLIC_PROMPT_MARKER not in data or hashlib.sha256(data).hexdigest() != PUBLIC_PROMPT_SHA256:
                raise ValueError("Root prompt must match the reviewed public variant; private or unreviewed content is not exportable")
    return paths


def export(destination, root=ROOT):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError("Export destination already exists; nothing was overwritten")
    if destination.is_relative_to(root):
        raise ValueError("Export must be outside the release repository")
    paths = inventory(root)
    destination.mkdir(parents=True)
    for rel in paths:
        output = destination / rel
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes((root / rel).read_bytes())
    for rel in paths:
        if hashlib.sha256((destination / rel).read_bytes()).digest() != hashlib.sha256((root / rel).read_bytes()).digest():
            raise ValueError("Export readback mismatch: " + str(rel))
    return len(paths)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print({"exported_files": export(args.destination), "history_included": False})
