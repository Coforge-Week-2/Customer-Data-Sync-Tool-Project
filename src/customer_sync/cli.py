"""Command-line entry point. Owner: Ansh.

Stub only. run_sync, format_summary, and main raise NotImplementedError.
Exit codes once implemented: 0 when the sync finishes (rejections allowed),
1 on SyncError, 2 on bad usage.
"""

from customer_sync.contracts import CustomerRepository, RecordSource, SyncSummary


def run_sync(source: RecordSource, repo: CustomerRepository) -> SyncSummary:
    """Fetch, clean, and store. Return added, updated, unchanged, and rejected."""
    raise NotImplementedError


def format_summary(s: SyncSummary, show_rejected: bool = True) -> str:
    """Render the sync summary, including one line per rejection."""
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run one sync, and print the summary."""
    raise NotImplementedError
