"""Fetch raw customer records. Owner: Vedant.

Stub only. Implementations raise NotImplementedError until the API tickets land.
"""

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests

from customer_sync.contracts import ApiError, RawRecord


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
        self.session = session if session is not None else requests.Session()
        self.sleep = sleep

    def fetch_page(self, page: int) -> list[RawRecord]:
        """Return one page of raw API records. Raises ApiError.

        Makes up to max_retries attempts, sleeping backoff * 2**(attempt-1) between them.
        Retries connection errors, timeouts, 5xx, 429 and 200 {"error": ...} bodies.
        Other failures (e.g. 404, invalid JSON) raise ApiError at once.
        """
        params: dict[str, str | int] = {"seed": self.seed, "results": self.results, "page": page}
        attempts = max(self.max_retries, 1)
        for attempt in range(1, attempts + 1):
            try:
                response = self.session.get(self.base_url, params=params, timeout=self.timeout)
                response.raise_for_status()
                payload = response.json()
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else 0
                if status != 429 and status < 500:
                    raise self._failure(page, attempt, exc) from exc
                cause: Exception = exc
            except (requests.ConnectionError, requests.Timeout) as exc:
                cause = exc
            except (requests.RequestException, ValueError) as exc:
                raise self._failure(page, attempt, exc) from exc
            else:
                if not (isinstance(payload, dict) and "error" in payload):
                    break
                cause = ValueError(f"error body: {payload['error']}")
            if attempt < attempts:
                self.sleep(self.backoff * 2 ** (attempt - 1))
        else:
            raise self._failure(page, attempts, cause) from cause
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            raise ApiError(f"page {page} from {self.base_url} has no 'results' list")
        return results

    def _failure(self, page: int, attempts: int, cause: Exception) -> ApiError:
        return ApiError(
            f"page {page} from {self.base_url} failed after {attempts} attempt(s): {cause}"
        )

    def fetch_records(self) -> list[RawRecord]:
        """Return raw records for every configured page. Raises ApiError."""
        return [r for page in range(1, self.pages + 1) for r in self.fetch_page(page)]


class FileSource:
    """Read a saved API response from disk. Raises SourceFileError."""

    def __init__(self, path: str | Path) -> None:
        self.path = path

    def fetch_records(self) -> list[RawRecord]:
        """Return the results list from a saved API response. Raises SourceFileError."""
        raise NotImplementedError
