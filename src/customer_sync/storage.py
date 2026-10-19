"""Store clean customers in SQLite. Owner: Nikita.

Stub only. Behavior methods raise NotImplementedError.
upsert_many runs as one transaction: all of the batch, or none of it.
Input uuids are unique; the cleaner guarantees that.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from types import TracebackType

from customer_sync.contracts import Customer, UpsertCounts


class CustomerStore:
    """SQLite customer repository. Use as a context manager."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = db_path

    def __enter__(self) -> CustomerStore:
        raise NotImplementedError

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        raise NotImplementedError

    def upsert_many(self, customers: Iterable[Customer]) -> UpsertCounts:
        """Insert new rows and update changed ones. Raises StorageError."""
        raise NotImplementedError

    def get(self, uuid: str) -> Customer | None:
        """Return one customer, or None when the uuid is absent."""
        raise NotImplementedError

    def all(self) -> list[Customer]:
        """Return every stored customer."""
        raise NotImplementedError

    def count(self) -> int:
        """Return how many customers are stored."""
        raise NotImplementedError

    def close(self) -> None:
        """Close the database connection."""
        raise NotImplementedError
