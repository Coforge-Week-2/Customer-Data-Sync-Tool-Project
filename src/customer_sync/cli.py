"""Command-line entry point. Owner: Ansh.

Wires fetch → clean → store, then prints a sync summary.
Exit codes: 0 when the sync finishes (rejections allowed),
1 on SyncError, 2 on bad usage (argparse).
"""

from __future__ import annotations

import argparse
import sys

from customer_sync.api_client import FileSource, RandomUserClient
from customer_sync.cleaning import clean_records
from customer_sync.contracts import (
    CustomerRepository,
    RecordSource,
    SyncError,
    SyncSummary,
)
from customer_sync.storage import CustomerStore


def run_sync(source: RecordSource, repo: CustomerRepository) -> SyncSummary:
    """Fetch, clean, and store. Return added, updated, unchanged, and rejected."""
    raws = source.fetch_records()
    result = clean_records(raws)
    counts = repo.upsert_many(result.accepted)
    return SyncSummary(
        added=counts.added,
        updated=counts.updated,
        unchanged=counts.unchanged,
        rejected=len(result.rejected),
        rejections=list(result.rejected),
    )


def _display_uuid(uuid: str | None) -> str:
    """Short uuid for summary lines; Missing when the cleaner had no uuid."""
    if uuid is None:
        return "Missing"
    return f"{uuid[:8]}…"


def format_summary(s: SyncSummary, show_rejected: bool = True) -> str:
    """Render the sync summary, including one line per rejection."""
    lines = [
        f"  added:      {s.added}",
        f"  updated:     {s.updated}",
        f"  unchanged:   {s.unchanged}",
        f"  rejected:    {s.rejected}",
    ]
    if show_rejected and s.rejections:
        lines.append("Rejected records:")
        for rejection in s.rejections:
            lines.append(
                f"  #{rejection.index}  uuid={_display_uuid(rejection.uuid)}  "
                f"{rejection.code}  {rejection.reason}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run one sync, and print the summary."""
    parser = argparse.ArgumentParser(prog="customer-sync")
    parser.add_argument("--from-file", default=None, metavar="PATH")
    parser.add_argument("--db", default="customers.db", metavar="PATH")
    parser.add_argument("--seed", default="team2")
    parser.add_argument("--results", type=int, default=50)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--quiet-rejections", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.from_file is not None:
            source: RecordSource = FileSource(args.from_file)
            source_label = f"file {args.from_file}"
        else:
            source = RandomUserClient(
                seed=args.seed,
                results=args.results,
                pages=args.pages,
            )
            source_label = f"api seed={args.seed}"
        with CustomerStore(args.db) as store:
            summary = run_sync(source, store)
    except SyncError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Sync complete (source: {source_label}, db: {args.db})")
    print(format_summary(summary, show_rejected=not args.quiet_rejections))
    return 0
