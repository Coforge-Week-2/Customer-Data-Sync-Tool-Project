"""Tests for the command-line entry point. Owner: Ansh."""

from collections.abc import Iterable

import pytest

from customer_sync.cli import format_summary, main, run_sync
from customer_sync.contracts import (
    ApiError,
    CleanResult,
    Customer,
    RawRecord,
    RejectCode,
    Rejection,
    SyncSummary,
    UpsertCounts,
)

RAW: RawRecord = {"login": {"uuid": "raw-1"}}

CUSTOMER = Customer(
    uuid="7a1c2b3d-4e5f-6789-abcd-ef0123456789",
    first_name="Ada",
    last_name="Lovelace",
    email="ada@example.com",
    phone=None,
    city=None,
    country=None,
    registered_at="2020-12-29T23:12:33Z",
)

REJECTION_WITH_UUID = Rejection(
    index=10,
    uuid="7a1c2b3d-4e5f-6789-abcd-ef0123456789",
    code=RejectCode.MISSING_FIELD,
    reason="missing field: email",
    raw=RAW,
)

REJECTION_NO_UUID = Rejection(
    index=11,
    uuid=None,
    code=RejectCode.MISSING_FIELD,
    reason="missing field: login.uuid",
    raw={},
)

COUNTS = UpsertCounts(added=1, updated=2, unchanged=3)


class FakeSource:
    """Stand-in for FileSource or RandomUserClient. No network, no disk."""

    def __init__(
        self,
        records: list[RawRecord] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.records = [] if records is None else records
        self.error = error

    def fetch_records(self) -> list[RawRecord]:
        if self.error is not None:
            raise self.error
        return self.records


class FakeRepo:
    """Stand-in for CustomerStore. Returns counts we choose."""

    def __init__(self, counts: UpsertCounts) -> None:
        self.counts = counts
        self.saved: list[Customer] = []

    def upsert_many(self, customers: Iterable[Customer]) -> UpsertCounts:
        self.saved = list(customers)
        return self.counts


def _clean_result(
    accepted: list[Customer] | None = None,
    rejected: list[Rejection] | None = None,
) -> CleanResult:
    return CleanResult(
        accepted=[] if accepted is None else accepted,
        rejected=[] if rejected is None else rejected,
    )


def _patch_main(
    monkeypatch: pytest.MonkeyPatch,
    clean: CleanResult,
    *,
    error: Exception | None = None,
    counts: UpsertCounts = COUNTS,
) -> dict[str, object]:
    """Replace file, API, cleaner, and database so main stays offline."""
    seen: dict[str, object] = {}

    class TrackingFileSource:
        def __init__(self, path: str) -> None:
            seen["file"] = path

        def fetch_records(self) -> list[RawRecord]:
            if error is not None:
                raise error
            return [RAW]

    class TrackingClient:
        def __init__(self, seed: str, results: int, pages: int) -> None:
            seen["api"] = (seed, results, pages)

        def fetch_records(self) -> list[RawRecord]:
            if error is not None:
                raise error
            return [RAW]

    class TrackingStore:
        def __init__(self, db_path: str) -> None:
            seen["db"] = db_path

        def __enter__(self) -> FakeRepo:
            return FakeRepo(counts)

        def __exit__(self, *_exc: object) -> None:
            return None

    monkeypatch.setattr("customer_sync.cli.FileSource", TrackingFileSource)
    monkeypatch.setattr("customer_sync.cli.RandomUserClient", TrackingClient)
    monkeypatch.setattr("customer_sync.cli.CustomerStore", TrackingStore)
    monkeypatch.setattr("customer_sync.cli.clean_records", lambda _raws: clean)
    return seen


def test_run_sync_sums_four_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    accepted = [CUSTOMER]
    rejected = [REJECTION_WITH_UUID, REJECTION_NO_UUID]

    def fake_clean(raws: list[RawRecord]) -> CleanResult:
        assert raws == [RAW]
        return _clean_result(accepted, rejected)

    monkeypatch.setattr("customer_sync.cli.clean_records", fake_clean)
    repo = FakeRepo(COUNTS)

    summary = run_sync(FakeSource([RAW]), repo)

    assert summary == SyncSummary(
        added=1,
        updated=2,
        unchanged=3,
        rejected=2,
        rejections=rejected,
    )
    assert repo.saved == accepted


def test_format_summary_matches_agreed_lines() -> None:
    summary = SyncSummary(
        added=10,
        updated=0,
        unchanged=0,
        rejected=2,
        rejections=[REJECTION_WITH_UUID, REJECTION_NO_UUID],
    )

    assert format_summary(summary) == (
        "  added:      10\n"
        "  updated:     0\n"
        "  unchanged:   0\n"
        "  rejected:    2\n"
        "Rejected records:\n"
        "  #10  uuid=7a1c2b3d…  missing_field  missing field: email\n"
        "  #11  uuid=Missing  missing_field  missing field: login.uuid"
    )


def test_main_returns_1_when_source_raises_api_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_main(monkeypatch, _clean_result(), error=ApiError("retries exhausted"))

    code = main([])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.err == "retries exhausted\n"
    assert "Sync complete" not in captured.out


def test_main_returns_1_when_client_constructor_raises_sync_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class BoomClient:
        def __init__(self, seed: str, results: int, pages: int) -> None:
            raise ApiError("client setup failed")

    monkeypatch.setattr("customer_sync.cli.RandomUserClient", BoomClient)

    code = main([])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.err == "client setup failed\n"
    assert "Sync complete" not in captured.out


def test_main_picks_file_source_or_api_client(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_main(monkeypatch, _clean_result())

    assert main([]) == 0
    assert seen["api"] == ("team2", 50, 1)
    assert "file" not in seen

    seen.clear()
    assert main(["--from-file", "day1.json"]) == 0
    assert seen["file"] == "day1.json"
    assert "api" not in seen


def test_main_prints_header_and_returns_0(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clean = _clean_result([CUSTOMER], [REJECTION_WITH_UUID])
    _patch_main(monkeypatch, clean, counts=UpsertCounts(added=1, updated=0, unchanged=0))

    code = main(["--db", "demo.db"])

    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("Sync complete (source: api seed=team2, db: demo.db)\n")
    assert "  added:      1" in out
    assert "Rejected records:" in out


def test_quiet_rejections_hides_detail_lines(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clean = _clean_result(rejected=[REJECTION_WITH_UUID, REJECTION_NO_UUID])
    _patch_main(monkeypatch, clean, counts=UpsertCounts(added=0, updated=0, unchanged=0))

    code = main(["--quiet-rejections"])

    out = capsys.readouterr().out
    assert code == 0
    assert "  rejected:    2" in out
    assert "Rejected records:" not in out
    assert "missing field" not in out
