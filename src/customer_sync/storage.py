"""Store clean customers in SQLite. Owner: Nikita.

Opening a store creates the customers table if it is absent and keeps any
existing rows. upsert_many runs as one transaction: all of the batch, or none of it.
Input uuids are unique; the cleaner guarantees that.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from types import TracebackType

from customer_sync.contracts import Customer, UpsertCounts

# Customer fields in contract order; rows are read back in this order.
_FIELDS = (
    "uuid",
    "first_name",
    "last_name",
    "email",
    "phone",
    "city",
    "country",
    "registered_at",
)
_SELECT = f"SELECT {', '.join(_FIELDS)} FROM customers"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    uuid TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    city TEXT,
    country TEXT,
    registered_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


class CustomerStore:
    """SQLite customer repository. Use as a context manager."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        with self._conn:
            self._conn.execute(_SCHEMA)

    def __enter__(self) -> CustomerStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def upsert_many(self, customers: Iterable[Customer]) -> UpsertCounts:
        """Insert new rows and update changed ones. Raises StorageError."""
        raise NotImplementedError

    def get(self, uuid: str) -> Customer | None:
        """Return one customer, or None when the uuid is absent."""
        row = self._conn.execute(f"{_SELECT} WHERE uuid = ?", (uuid,)).fetchone()
        return None if row is None else Customer(*row)

    def all(self) -> list[Customer]:
        """Return every stored customer, ordered by uuid."""
        rows = self._conn.execute(f"{_SELECT} ORDER BY uuid").fetchall()
        return [Customer(*row) for row in rows]

    def count(self) -> int:
        """Return how many customers are stored."""
        (total,) = self._conn.execute("SELECT COUNT(*) FROM customers").fetchone()
        return int(total)

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
