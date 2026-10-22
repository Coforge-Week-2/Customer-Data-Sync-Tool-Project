"""End-to-end sync test. Owner: Ansh.

Saved response -> clean -> temp SQLite -> summary.
"""

from pathlib import Path

import pytest

from customer_sync.api_client import FileSource
from customer_sync.cli import main, run_sync
from customer_sync.contracts import SyncSummary
from customer_sync.storage import CustomerStore


def _counts(summary: SyncSummary) -> tuple[int, int, int, int]:
    return (summary.added, summary.updated, summary.unchanged, summary.rejected)


@pytest.mark.integration
def test_day1_then_day2_on_same_database(fixtures_dir: Path, tmp_path: Path) -> None:
    """Empty database, then the edited day-2 file on that same database."""
    day1 = fixtures_dir / "integration" / "day1.json"
    day2 = fixtures_dir / "integration" / "day2_edited.json"
    with CustomerStore(tmp_path / "test.db") as store:
        first = run_sync(FileSource(day1), store)
        second = run_sync(FileSource(day2), store)
    assert _counts(first) == (10, 0, 0, 2)
    assert _counts(second) == (1, 1, 9, 2)


@pytest.mark.integration
def test_day1_second_run_is_unchanged(fixtures_dir: Path, tmp_path: Path) -> None:
    """Running day1 again stores nothing new."""
    path = fixtures_dir / "integration" / "day1.json"
    with CustomerStore(tmp_path / "test.db") as store:
        run_sync(FileSource(path), store)
        second = run_sync(FileSource(path), store)
    assert _counts(second) == (0, 0, 10, 2)


@pytest.mark.integration
def test_main_from_file_returns_zero(fixtures_dir: Path, tmp_path: Path) -> None:
    """The CLI finishes a from-file sync with exit code 0."""
    path = str(fixtures_dir / "integration" / "day1.json")
    assert main(["--from-file", path, "--db", str(tmp_path / "cli.db")]) == 0
