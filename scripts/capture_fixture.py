"""Capture a Random User API response into a fixture file. Owner: Vedant.

Never run in CI. Commands used for the committed fixtures (run from the repo root;
defaults are --seed team2 --results 5):
    python scripts/capture_fixture.py tests/fixtures/api/page1.json --page 1
    python scripts/capture_fixture.py tests/fixtures/api/page2.json --page 2
error_body.json in the same folder is hand-written (the API sometimes returns it with status 200).
"""

import argparse
import json
from pathlib import Path

import requests

BASE_URL = "https://randomuser.me/api/1.4/"


def main(argv: list[str] | None = None) -> int:
    """Save one API response as pretty-printed JSON at the given path."""
    p = argparse.ArgumentParser(description="Save a Random User API response as JSON.")
    p.add_argument("path", type=Path, help="where to save the JSON")
    p.add_argument("--seed", default="team2")
    p.add_argument("--results", type=int, default=5)
    p.add_argument("--page", type=int, default=1)
    args = p.parse_args(argv)

    resp = requests.get(
        BASE_URL,
        params={"seed": args.seed, "results": args.results, "page": args.page},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    args.path.parent.mkdir(parents=True, exist_ok=True)
    args.path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"saved {len(data.get('results', []))} records to {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
