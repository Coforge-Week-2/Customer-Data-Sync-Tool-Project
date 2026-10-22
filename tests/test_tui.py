"""Tests for the terminal UI. Owner: Vedant.

Each test drives the real app in-process with Textual's test driver,
using saved fixtures and a temporary database, so nothing touches the network.
"""

import asyncio
from pathlib import Path

from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Digits, Input, RichLog, TabbedContent

from customer_sync.tui import COUNTS, SyncApp


async def _run_sync(pilot: Pilot[None], path: Path | str, db: Path) -> None:
    """Fill the form, press Run, and wait until the worker has updated the screen."""
    app = pilot.app
    app.query_one("#path", Input).value = str(path)
    app.query_one("#db", Input).value = str(db)
    app.query_one("#run", Button).press()
    await pilot.pause()  # let the press handler start the worker
    await app.workers.wait_for_complete()
    await pilot.pause()


def _counts(app: SyncApp) -> tuple[int, ...]:
    return tuple(int(app.query_one(f"#{name}", Digits).value) for name in COUNTS)


async def _log_text(pilot: Pilot[None]) -> str:
    """Open the Run log tab (a hidden log keeps its lines until shown) and read it."""
    pilot.app.query_one(TabbedContent).active = "log-tab"
    await pilot.pause()
    return "\n".join(line.text for line in pilot.app.query_one("#log", RichLog).lines)


def test_file_sync_shows_counts_rejections_and_rows(fixtures_dir: Path, tmp_path: Path) -> None:
    async def scenario() -> None:
        app = SyncApp()
        async with app.run_test(size=(140, 40)) as pilot:
            await _run_sync(pilot, fixtures_dir / "integration" / "day1.json", tmp_path / "t.db")
            assert _counts(app) == (10, 0, 0, 2)
            assert app.query_one("#rejections", DataTable).row_count == 2
            assert app.query_one("#customers", DataTable).row_count == 10
            assert "10 added" in await _log_text(pilot)
            assert not app.query_one("#run", Button).disabled

    asyncio.run(scenario())


def test_second_file_on_same_database_shows_update(fixtures_dir: Path, tmp_path: Path) -> None:
    async def scenario() -> None:
        app = SyncApp()
        db = tmp_path / "t.db"
        async with app.run_test(size=(140, 40)) as pilot:
            await _run_sync(pilot, fixtures_dir / "integration" / "day1.json", db)
            await _run_sync(pilot, fixtures_dir / "integration" / "day2_edited.json", db)
            assert _counts(app) == (1, 1, 9, 2)
            assert app.query_one("#customers", DataTable).row_count == 11

    asyncio.run(scenario())


def test_missing_file_shows_error_and_keeps_counts(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = SyncApp()
        async with app.run_test(size=(140, 40)) as pilot:
            await _run_sync(pilot, tmp_path / "nope.json", tmp_path / "t.db")
            assert _counts(app) == (0, 0, 0, 0)
            assert "cannot read" in await _log_text(pilot)
            assert not app.query_one("#run", Button).disabled

    asyncio.run(scenario())


def test_api_source_rejects_zero_pages_without_syncing(tmp_path: Path) -> None:
    async def scenario() -> None:
        app = SyncApp()
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.click("#api")
            assert app.query_one("#path", Input).disabled
            app.query_one("#pages", Input).value = "0"
            app.query_one("#db", Input).value = str(tmp_path / "t.db")
            app.query_one("#run", Button).press()
            await pilot.pause()
            assert not app.workers  # nothing started, so nothing touched the network
            assert not (tmp_path / "t.db").exists()

    asyncio.run(scenario())
