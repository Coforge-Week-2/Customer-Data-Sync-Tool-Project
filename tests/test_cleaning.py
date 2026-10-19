"""Tests for cleaning and validation. Owner: Julian."""
import copy

import pytest

from customer_sync.cleaning import RecordRejected, clean_record
from customer_sync.contracts import Customer, RawRecord, RejectCode


@pytest.fixture
def raw(raw_records: list[RawRecord]) -> RawRecord:
    """A fresh copy of one valid record, safe to mutate in a test."""
    return copy.deepcopy(raw_records[0])


def test_valid_record_maps_to_customer(raw: RawRecord) -> None:
    assert clean_record(raw) == Customer(
        uuid="18d3d4f8-1b6c-480d-be6f-51de14bc1017",
        first_name="Beaudine",
        last_name="Ottevanger",
        email="beaudine.ottevanger@example.com",
        phone="(026) 7000444",
        city="Zwarsluis",
        country="Netherlands",
        registered_at="2020-12-29T23:12:33Z",
    )

def test_email_wrong_type_is_rejected(raw: RawRecord) -> None:
    raw["email"] = 123
    with pytest.raises(RecordRejected) as exc:
        clean_record(raw)
    assert exc.value.code == RejectCode.WRONG_TYPE
    assert "email" in exc.value.reason