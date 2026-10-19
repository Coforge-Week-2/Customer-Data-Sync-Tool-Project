"""Skeleton guard: modules import, contracts exist, and the raw fixture has 10 records."""

from dataclasses import fields
from typing import get_type_hints

import customer_sync.api_client as api_client
import customer_sync.cleaning as cleaning
import customer_sync.cli as cli
import customer_sync.storage as storage
from customer_sync.contracts import (
    CleanResult,
    Customer,
    RawRecord,
    RejectCode,
    Rejection,
    SyncSummary,
    UpsertCounts,
)


def test_modules_import() -> None:
    assert api_client.RandomUserClient is not None
    assert api_client.FileSource is not None
    assert cleaning.clean_record is not None
    assert cleaning.clean_records is not None
    assert cleaning.RecordRejected is not None
    assert storage.CustomerStore is not None
    assert cli.run_sync is not None
    assert cli.format_summary is not None
    assert cli.main is not None


def test_contracts_exist() -> None:
    assert Customer is not None
    assert Rejection is not None
    assert CleanResult is not None
    assert UpsertCounts is not None
    assert SyncSummary is not None


def test_customer_shape() -> None:
    names = [item.name for item in fields(Customer)]
    assert names == [
        "uuid",
        "first_name",
        "last_name",
        "email",
        "phone",
        "city",
        "country",
        "registered_at",
    ]
    hints = get_type_hints(Customer)
    assert hints["uuid"] is str
    assert hints["first_name"] is str
    assert hints["last_name"] is str
    assert hints["email"] is str
    assert hints["phone"] == str | None
    assert hints["city"] == str | None
    assert hints["country"] == str | None
    assert hints["registered_at"] is str


def test_reject_codes() -> None:
    assert [code.value for code in RejectCode] == [
        "missing_field",
        "wrong_type",
        "invalid_value",
        "duplicate",
    ]


def test_raw_fixture_has_ten_records(raw_records: list[RawRecord]) -> None:
    assert len(raw_records) == 10
    for record in raw_records:
        uuid = record["login"]["uuid"]
        assert isinstance(uuid, str)
        assert uuid
