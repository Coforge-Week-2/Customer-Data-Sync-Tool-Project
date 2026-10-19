"""Store clean customers in SQLite. Owner: Nikita.

Opening a store creates the customers table if it is absent and keeps any
existing rows. upsert_many runs as one transaction: all of the batch, or none of it.
Input uuids are unique; the cleaner guarantees that.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
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
_INSERT = (
    f"INSERT INTO customers ({', '.join(_FIELDS)}, created_at, updated_at) "
    f"VALUES ({', '.join('?' * (len(_FIELDS) + 2))})"
)
# Every field except uuid, then updated_at; created_at is never touched.
_UPDATE = (
    f"UPDATE customers SET {', '.join(f'{name} = ?' for name in _FIELDS[1:])}, "
    "updated_at = ? WHERE uuid = ?"
)

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


def _values(customer: Customer) -> tuple[str | None, ...]:
    """Customer fields in _FIELDS order."""
    return tuple(getattr(customer, name) for name in _FIELDS)


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
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        added = updated = unchanged = 0
        with self._conn:
            for customer in customers:
                existing = self.get(customer.uuid)
                if existing is None:
                    self._conn.execute(_INSERT, (*_values(customer), now, now))
                    added += 1
                elif existing != customer:
                    self._conn.execute(_UPDATE, (*_values(customer)[1:], now, customer.uuid))
                    updated += 1
                else:
                    unchanged += 1
        return UpsertCounts(added=added, updated=updated, unchanged=unchanged)

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
