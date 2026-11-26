"""Import a reviewed public employer snapshot. Dry-run by default, never scans boards."""
import argparse
from pathlib import Path
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills/workhunt-search/scripts"))
from source_registry import update_registry, UPSTREAM_URL, UPSTREAM_REVISION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=ROOT)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--snapshot", type=Path)
    source.add_argument("--network", action="store_true", help="Explicitly authorized download of the selected upstream snapshot only")
    parser.add_argument("--source-url", default=UPSTREAM_URL)
    parser.add_argument("--revision", default=UPSTREAM_REVISION)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--check", action="store_true", help="Exit 1 if the import would change registry content")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workhunt-source-import-") as folder:
        path = args.snapshot
        if args.network:
            if not args.source_url.startswith("https://raw.githubusercontent.com/ahiraz/israel-job-search/"):
                parser.error("Network import supports the attributed upstream repository only; use --snapshot for another reviewed local input")
            path = Path(folder) / "companies.json"
            with urllib.request.urlopen(args.source_url, timeout=30) as response:
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError("Registry snapshot exceeds bounded input size")
            path.write_bytes(data)
        result = update_registry(args.workspace, path, args.apply, args.source_url, args.revision)
        print(result)
        return 1 if args.check and result["changed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
