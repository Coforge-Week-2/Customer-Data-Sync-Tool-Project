"""Tests for SQLite storage. Owner: Nikita."""

import re
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest

from customer_sync.contracts import Customer, StorageError, UpsertCounts
from customer_sync.storage import CustomerStore

NOW = "2026-10-19T12:00:00Z"


BASE = Customer(
    uuid="uuid-1",
    first_name="Ada",
    last_name="Lovelace",
    email="ada@example.com",
    phone="0123456789",
    city="London",
    country="United Kingdom",
    registered_at="2020-12-29T23:12:33Z",
)


def make_customer(uuid: str = "uuid-1", **overrides: str | None) -> Customer:
    return replace(BASE, uuid=uuid, **overrides)


def insert_row(db_path: Path, customer: Customer) -> None:
    """Write a row with plain sqlite3, bypassing the store."""
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                customer.uuid,
                customer.first_name,
                customer.last_name,
                customer.email,
                customer.phone,
                customer.city,
                customer.country,
                customer.registered_at,
                NOW,
                NOW,
            ),
        )


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


def test_new_database_has_empty_customers_table(db_path: Path) -> None:
    with CustomerStore(db_path) as store:
        assert store.count() == 0
        assert store.all() == []

    with closing(sqlite3.connect(db_path)) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'customers'"
        ).fetchall()
    assert tables == [("customers",)]


def test_reopening_keeps_existing_rows(db_path: Path) -> None:
    CustomerStore(db_path).close()
    customer = make_customer(phone=None, city=None, country=None)
    insert_row(db_path, customer)

    with CustomerStore(db_path) as store:
        assert store.count() == 1
        assert store.get("uuid-1") == customer


def test_get_unknown_uuid_returns_none(db_path: Path) -> None:
    with CustomerStore(db_path) as store:
        assert store.get("unknown") is None


def test_all_returns_customers_ordered_by_uuid(db_path: Path) -> None:
    CustomerStore(db_path).close()
    b = make_customer("b", email="b@example.com")
    a = make_customer("a", email="a@example.com")
    insert_row(db_path, b)
    insert_row(db_path, a)

    with CustomerStore(db_path) as store:
        assert store.all() == [a, b]
        assert store.count() == 2


def test_context_manager_closes_connection(db_path: Path) -> None:
    with CustomerStore(db_path) as store:
        assert store.count() == 0

    with pytest.raises(sqlite3.ProgrammingError):
        store.count()


def test_close_without_context_manager(db_path: Path) -> None:
    store = CustomerStore(db_path)
    store.close()

    with pytest.raises(sqlite3.ProgrammingError):
        store.count()


def three_customers() -> list[Customer]:
    return [
        make_customer("a", email="a@example.com"),
        make_customer("b", email="b@example.com", phone=None, city=None, country=None),
        make_customer("c", email="c@example.com"),
    ]


def timestamps(db_path: Path, uuid: str) -> tuple[str, str]:
    """Return (created_at, updated_at) for one row, read with plain sqlite3."""
    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute(
            "SELECT created_at, updated_at FROM customers WHERE uuid = ?", (uuid,)
        ).fetchone()
    return row[0], row[1]


def backdate(db_path: Path, uuid: str) -> None:
    """Set both timestamps to a fixed past value so later changes are visible."""
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute(
            "UPDATE customers SET created_at = ?, updated_at = ? WHERE uuid = ?",
            (NOW, NOW, uuid),
        )


def test_upsert_new_customers_are_added(db_path: Path) -> None:
    with CustomerStore(db_path) as store:
        counts = store.upsert_many(three_customers())
        assert counts == UpsertCounts(added=3, updated=0, unchanged=0)
        assert store.all() == three_customers()

    created_at, updated_at = timestamps(db_path, "a")
    assert created_at == updated_at
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", created_at)


def test_upsert_same_customers_again_is_unchanged(db_path: Path) -> None:
    with CustomerStore(db_path) as store:
        store.upsert_many(three_customers())
        counts = store.upsert_many(three_customers())
        assert counts == UpsertCounts(added=0, updated=0, unchanged=3)
        assert store.count() == 3


def test_upsert_changed_phone_is_updated(db_path: Path) -> None:
    customers = three_customers()
    with CustomerStore(db_path) as store:
        store.upsert_many(customers)
        customers[0] = replace(customers[0], phone="000")
        counts = store.upsert_many(customers)
        assert counts == UpsertCounts(added=0, updated=1, unchanged=2)
        assert store.get("a") == customers[0]
        assert store.count() == 3


def test_update_keeps_created_at_and_moves_updated_at(db_path: Path) -> None:
    with CustomerStore(db_path) as store:
        store.upsert_many([make_customer("a")])
        backdate(db_path, "a")
        store.upsert_many([make_customer("a", city="Paris")])

    created_at, updated_at = timestamps(db_path, "a")
    assert created_at == NOW
    assert updated_at != NOW


def test_unchanged_run_keeps_updated_at(db_path: Path) -> None:
    with CustomerStore(db_path) as store:
        store.upsert_many([make_customer("a")])
        backdate(db_path, "a")
        store.upsert_many([make_customer("a")])

    assert timestamps(db_path, "a") == (NOW, NOW)


def test_upsert_mixed_batch(db_path: Path) -> None:
    same = make_customer("same", email="same@example.com")
    changed = make_customer("changed", email="changed@example.com")
    new = make_customer("new", email="new@example.com")
    with CustomerStore(db_path) as store:
        store.upsert_many([same, changed])
        counts = store.upsert_many(iter([same, replace(changed, last_name="Byron"), new]))
        assert counts == UpsertCounts(added=1, updated=1, unchanged=1)
        assert store.get("changed") == replace(changed, last_name="Byron")
        assert store.count() == 3


def test_upsert_empty_batch(db_path: Path) -> None:
    with CustomerStore(db_path) as store:
        assert store.upsert_many([]) == UpsertCounts(added=0, updated=0, unchanged=0)


def test_upsert_is_idempotent(db_path: Path) -> None:
    customers = [make_customer(f"u{i:02}", email=f"u{i}@example.com") for i in range(10)]
    with CustomerStore(db_path) as store:
        results = [store.upsert_many(customers) for _ in range(3)]
        assert results[0] == UpsertCounts(added=10, updated=0, unchanged=0)
        assert results[-1] == UpsertCounts(added=0, updated=0, unchanged=10)
        assert store.count() == 10


def test_failure_mid_batch_rolls_back_everything(db_path: Path) -> None:
    first = make_customer("first", email="first@example.com")
    second = make_customer("second", email="second@example.com")
    batch = [
        replace(first, phone="000"),
        make_customer("new-1", email="new1@example.com"),
        make_customer("new-2", email="new2@example.com"),
        make_customer("bad", email=None),
        make_customer("new-3", email="new3@example.com"),
    ]
    with CustomerStore(db_path) as store:
        store.upsert_many([first, second])

        with pytest.raises(StorageError, match="nothing was written"):
            store.upsert_many(batch)

        assert store.all() == [first, second]
        # The store is still usable after a failed batch.
        assert store.upsert_many([first, second]) == UpsertCounts(0, 0, 2)


def test_open_directory_raises_storage_error(tmp_path: Path) -> None:
    with pytest.raises(StorageError, match="could not open database"):
        CustomerStore(tmp_path)


def test_open_missing_folder_raises_storage_error(tmp_path: Path) -> None:
    with pytest.raises(StorageError, match="could not open database"):
        CustomerStore(tmp_path / "missing" / "test.db")


def test_open_non_database_file_raises_storage_error(tmp_path: Path) -> None:
    not_a_db = tmp_path / "notes.db"
    not_a_db.write_text("this is not a sqlite database " * 10, encoding="utf-8")
    with pytest.raises(StorageError, match="could not open database"):
        CustomerStore(not_a_db)
