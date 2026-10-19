"""Tests for the API client. Owner: Vedant."""

import json
from pathlib import Path
from typing import Any

import pytest

from customer_sync.api_client import RandomUserClient
from customer_sync.contracts import ApiError

API_FIXTURES = Path(__file__).parent / "fixtures" / "api"


def load(name: str) -> dict[str, Any]:
    return json.loads((API_FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        pass

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
    [load("error_body.json"), {"results": "nope"}, ["not", "a", "dict"]],
)
def test_missing_or_bad_results_raises_api_error(payload: Any) -> None:
    client = RandomUserClient(session=FakeSession({1: payload}))
    with pytest.raises(ApiError, match="results"):
        client.fetch_page(1)
