"""Fetch raw customer records. Owner: Vedant.

Stub only. Implementations raise NotImplementedError until the API tickets land.
"""

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from customer_sync.contracts import RawRecord


class RandomUserClient:
    """Paged Random User API client.

    fetch_page and fetch_records return raw result records.
    They raise ApiError when retries are exhausted or the response is unusable.
    session and sleep are injectable so tests stay offline.
    """

    def __init__(
        self,
        base_url: str = "https://randomuser.me/api/1.4/",
        seed: str = "team2",
        results: int = 50,
        pages: int = 1,
        max_retries: int = 3,
        backoff: float = 0.5,
        timeout: float = 10.0,
        session: Any = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url
        self.seed = seed
        self.results = results
        self.pages = pages
        self.max_retries = max_retries
        self.backoff = backoff
        self.timeout = timeout
        self.session = session
        self.sleep = sleep

    def fetch_page(self, page: int) -> list[RawRecord]:
        """Return one page of raw API records. Raises ApiError."""
        raise NotImplementedError

    def fetch_records(self) -> list[RawRecord]:
        """Return raw records for every configured page. Raises ApiError."""
        raise NotImplementedError


class FileSource:
    """Read a saved API response from disk. Raises SourceFileError."""

    def __init__(self, path: str | Path) -> None:
        self.path = path

    def fetch_records(self) -> list[RawRecord]:
        """Return the results list from a saved API response. Raises SourceFileError."""
        raise NotImplementedError
