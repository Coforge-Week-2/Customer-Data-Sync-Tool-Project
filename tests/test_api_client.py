"""Tests for the API client. Owner: Vedant."""

import json
from pathlib import Path
from typing import Any

import pytest
import requests

from customer_sync.api_client import FileSource, RandomUserClient
from customer_sync.contracts import ApiError, SourceFileError

API_FIXTURES = Path(__file__).parent / "fixtures" / "api"
RAW_FIXTURE = Path(__file__).parent / "fixtures" / "raw" / "seed_team2_r10_p1.json"


def load(name: str) -> dict[str, Any]:
    return json.loads((API_FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, payload: Any = None, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error", response=self)  # type: ignore[arg-type]

    def json(self) -> Any:
        return self.payload


class FakeSession:
    """Serves page<N>.json by the requested page param and records every call."""

    def __init__(self, payloads: dict[int, Any] | None = None) -> None:
        self.payloads = payloads or {1: load("page1.json"), 2: load("page2.json")}
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, params: dict[str, Any], timeout: float) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse(self.payloads[params["page"]])


def test_fetch_page_sends_params_and_returns_results() -> None:
    session = FakeSession()
    client = RandomUserClient(seed="team2", results=5, timeout=7.0, session=session)

    records = client.fetch_page(1)

    assert records == load("page1.json")["results"]
    assert session.calls == [
        {
            "url": "https://randomuser.me/api/1.4/",
            "params": {"seed": "team2", "results": 5, "page": 1},
            "timeout": 7.0,
        }
    ]


def test_fetch_records_concatenates_pages_in_order() -> None:
    session = FakeSession()
    client = RandomUserClient(results=5, pages=2, session=session)

    records = client.fetch_records()

    assert records == load("page1.json")["results"] + load("page2.json")["results"]
    assert [c["params"]["page"] for c in session.calls] == [1, 2]


def test_fetch_records_default_is_single_page() -> None:
    session = FakeSession()
    RandomUserClient(results=5, session=session).fetch_records()
    assert len(session.calls) == 1


@pytest.mark.parametrize(
    "payload",
    [{"results": "nope"}, ["not", "a", "dict"]],
)
def test_missing_or_bad_results_raises_api_error(payload: Any) -> None:
    client = RandomUserClient(session=FakeSession({1: payload}))
    with pytest.raises(ApiError, match="results"):
        client.fetch_page(1)


class ScriptedSession:
    """Plays back outcomes (a FakeResponse or an exception to raise); the last one repeats."""

    def __init__(self, *outcomes: FakeResponse | Exception) -> None:
        self.outcomes = outcomes
        self.calls = 0

    def get(self, url: str, params: dict[str, Any], timeout: float) -> FakeResponse:
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


OK = FakeResponse(load("page1.json"))
OK_RECORDS = load("page1.json")["results"]
UNAVAILABLE = FakeResponse(status_code=503)


def make_client(session: ScriptedSession, delays: list[float], **kwargs: Any) -> RandomUserClient:
    return RandomUserClient(session=session, sleep=delays.append, **kwargs)


def test_succeeds_on_third_attempt_after_two_sleeps() -> None:
    delays: list[float] = []
    session = ScriptedSession(requests.ConnectionError("down"), UNAVAILABLE, OK)

    records = make_client(session, delays).fetch_page(1)

    assert records == OK_RECORDS
    assert session.calls == 3
    assert delays == [0.5, 1.0]


@pytest.mark.parametrize(
    "failure",
    [
        requests.ConnectionError("refused"),
        requests.Timeout("slow"),
        FakeResponse(status_code=500),
        FakeResponse(status_code=503),
        FakeResponse(status_code=429),
        FakeResponse(load("error_body.json")),
    ],
)
def test_transient_failures_are_retried(failure: FakeResponse | Exception) -> None:
    delays: list[float] = []
    session = ScriptedSession(failure, OK)

    assert make_client(session, delays).fetch_page(1) == OK_RECORDS
    assert session.calls == 2
    assert delays == [0.5]


def test_gives_up_after_max_retries_with_clear_error() -> None:
    delays: list[float] = []
    session = ScriptedSession(UNAVAILABLE)
    client = make_client(session, delays, max_retries=3)

    with pytest.raises(ApiError) as excinfo:
        client.fetch_page(1)

    assert session.calls == 3
    assert delays == [0.5, 1.0]  # no sleep after the final attempt
    message = str(excinfo.value)
    assert "https://randomuser.me/api/1.4/" in message
    assert "3 attempt" in message
    assert "503" in message
    assert isinstance(excinfo.value.__cause__, requests.HTTPError)


def test_error_body_is_retried_then_reported() -> None:
    delays: list[float] = []
    session = ScriptedSession(FakeResponse(load("error_body.json")))

    with pytest.raises(ApiError, match="3 attempt.*error body"):
        make_client(session, delays).fetch_page(1)

    assert session.calls == 3
    assert delays == [0.5, 1.0]


@pytest.mark.parametrize(
    "failure",
    [
        FakeResponse(status_code=404),
        FakeResponse(status_code=400),
        requests.exceptions.InvalidURL("bad"),
    ],
)
def test_non_transient_failures_are_not_retried(failure: FakeResponse | Exception) -> None:
    delays: list[float] = []
    session = ScriptedSession(failure)

    with pytest.raises(ApiError, match="1 attempt"):
        make_client(session, delays).fetch_page(1)

    assert session.calls == 1
    assert delays == []


def test_backoff_doubles_each_attempt() -> None:
    delays: list[float] = []
    session = ScriptedSession(UNAVAILABLE)

    with pytest.raises(ApiError):
        make_client(session, delays, max_retries=5, backoff=0.25).fetch_page(1)

    assert delays == [0.25, 0.5, 1.0, 2.0]


def test_file_source_returns_results_from_saved_response() -> None:
    records = FileSource(RAW_FIXTURE).fetch_records()

    assert records == json.loads(RAW_FIXTURE.read_text(encoding="utf-8"))["results"]
    assert len(records) == 10


def test_file_source_accepts_str_path(tmp_path: Path) -> None:
    saved = tmp_path / "saved.json"
    saved.write_text(json.dumps({"results": [{"a": 1}]}), encoding="utf-8")

    assert FileSource(str(saved)).fetch_records() == [{"a": 1}]


def test_file_source_missing_file_names_the_path(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"

    with pytest.raises(SourceFileError, match="nope.json"):
        FileSource(missing).fetch_records()


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("{not json", "not valid JSON"),
        ("", "not valid JSON"),
        ('{"info": {}}', "results"),
        ('{"results": "nope"}', "results"),
        ('["not", "a", "dict"]', "results"),
    ],
)
def test_file_source_bad_content_raises(tmp_path: Path, content: str, match: str) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(content, encoding="utf-8")

    with pytest.raises(SourceFileError, match=match):
        FileSource(bad).fetch_records()


def test_file_source_non_utf8_file_raises(tmp_path: Path) -> None:
    bad = tmp_path / "latin1.json"
    bad.write_bytes(b'{"results": ["\xe9"]}')

    with pytest.raises(SourceFileError, match="bad.json|latin1.json"):
        FileSource(bad).fetch_records()
