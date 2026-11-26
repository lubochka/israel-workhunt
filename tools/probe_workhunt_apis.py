"""Explicit bounded public API checks; import has no network or file side effects."""
import argparse
import datetime as dt
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills/workhunt-search/scripts"))
from profile_config import load_profile, private_root
from scan import collect_boards, fetch
from records import save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--network", action="store_true", required=True)
    args = parser.parse_args()
    profile = load_profile(args.workspace)
    root = private_root(args.workspace)
    boards, errors = collect_boards(profile, root)
    selected = {}
    for board in boards:
        selected.setdefault(board["provider"], board)
    result = {"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(), "scope": "At most one explicitly configured public board per provider", "discovery_errors": errors, "providers": []}
    for provider, board in selected.items():
        row = {"provider": provider, "board_key": board["key"]}
        try:
            jobs = fetch(board)
            row.update(status="parsed", records=len(jobs), partial=bool(getattr(jobs, "errors", [])))
        except Exception as exc:
            row.update(status="failed", error_type=type(exc).__name__)
        result["providers"].append(row)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    output = root / "validation" / ("api-probe-" + stamp + ".json")
    save(output, result)
    print(output)


if __name__ == "__main__":
    main()
