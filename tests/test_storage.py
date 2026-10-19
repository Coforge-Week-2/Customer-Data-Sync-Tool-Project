"""Tests for SQLite storage. Owner: Nikita."""

import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest

from customer_sync.contracts import Customer
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
