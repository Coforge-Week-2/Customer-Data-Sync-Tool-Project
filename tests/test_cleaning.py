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


def test_email_missing_is_rejected(raw: RawRecord) -> None:
    del raw["email"]
    with pytest.raises(RecordRejected) as exc:
        clean_record(raw)
    assert exc.value.code == RejectCode.MISSING_FIELD
    assert "email" in exc.value.reason


@pytest.mark.parametrize(
    "bad_email",
    ["no-at-sign.com", "a@b", "a @b.com", "a@@b.com", "", "   "],
)
def test_email_malformed_is_rejected(raw: RawRecord, bad_email: str) -> None:
    raw["email"] = bad_email
    with pytest.raises(RecordRejected) as exc:
        clean_record(raw)
    assert exc.value.code == RejectCode.INVALID_VALUE
    assert "email" in exc.value.reason


def test_email_is_trimmed_and_lowercased(raw: RawRecord) -> None:
    raw["email"] = "  Foo@BAR.com "
    assert clean_record(raw).email == "foo@bar.com"


@pytest.mark.parametrize("field", ["first", "last"])
def test_name_missing_is_rejected(raw: RawRecord, field: str) -> None:
    del raw["name"][field]
    with pytest.raises(RecordRejected) as exc:
        clean_record(raw)
    assert exc.value.code == RejectCode.MISSING_FIELD
    assert f"{field}_name" in exc.value.reason


def test_name_object_missing_is_rejected(raw: RawRecord) -> None:
    del raw["name"]
    with pytest.raises(RecordRejected) as exc:
        clean_record(raw)
    assert exc.value.code == RejectCode.MISSING_FIELD


@pytest.mark.parametrize("field", ["first", "last"])
def test_name_wrong_type_is_rejected(raw: RawRecord, field: str) -> None:
    raw["name"][field] = 42
    with pytest.raises(RecordRejected) as exc:
        clean_record(raw)
    assert exc.value.code == RejectCode.WRONG_TYPE
    assert f"{field}_name" in exc.value.reason


@pytest.mark.parametrize("field", ["first", "last"])
@pytest.mark.parametrize("blank", ["", "   "])
def test_name_blank_is_rejected(raw: RawRecord, field: str, blank: str) -> None:
    raw["name"][field] = blank
    with pytest.raises(RecordRejected) as exc:
        clean_record(raw)
    assert exc.value.code == RejectCode.INVALID_VALUE
    assert f"{field}_name" in exc.value.reason


def test_name_is_trimmed(raw: RawRecord) -> None:
    raw["name"]["first"] = "  Beaudine "
    raw["name"]["last"] = " Ottevanger  "
    customer = clean_record(raw)
    assert customer.first_name == "Beaudine"
    assert customer.last_name == "Ottevanger"


def test_uuid_missing_is_rejected(raw: RawRecord) -> None:
    del raw["login"]["uuid"]
    with pytest.raises(RecordRejected) as exc:
        clean_record(raw)
    assert exc.value.code == RejectCode.MISSING_FIELD
    assert "uuid" in exc.value.reason


def test_login_object_missing_is_rejected(raw: RawRecord) -> None:
    del raw["login"]
    with pytest.raises(RecordRejected) as exc:
        clean_record(raw)
    assert exc.value.code == RejectCode.MISSING_FIELD


def test_uuid_wrong_type_is_rejected(raw: RawRecord) -> None:
    raw["login"]["uuid"] = 42
    with pytest.raises(RecordRejected) as exc:
        clean_record(raw)
    assert exc.value.code == RejectCode.WRONG_TYPE
    assert "uuid" in exc.value.reason


@pytest.mark.parametrize(
    "bad_uuid",
    [
        "not-a-uuid",
        "",
        "   ",
        "18d3d4f8-1b6c-480d-be6f-51de14bc101",
        "{18d3d4f8-1b6c-480d-be6f-51de14bc1017}",
        "18d3d4f81b6c480dbe6f51de14bc1017",
    ],
)
def test_uuid_malformed_is_rejected(raw: RawRecord, bad_uuid: str) -> None:
    raw["login"]["uuid"] = bad_uuid
    with pytest.raises(RecordRejected) as exc:
        clean_record(raw)
    assert exc.value.code == RejectCode.INVALID_VALUE
    assert "uuid" in exc.value.reason


def test_uuid_is_trimmed_and_lowercased(raw: RawRecord) -> None:
    raw["login"]["uuid"] = "  18D3D4F8-1B6C-480D-BE6F-51DE14BC1017 "
    assert clean_record(raw).uuid == "18d3d4f8-1b6c-480d-be6f-51de14bc1017"


def test_registered_date_missing_is_rejected(raw: RawRecord) -> None:
    del raw["registered"]["date"]
    with pytest.raises(RecordRejected) as exc:
        clean_record(raw)
    assert exc.value.code == RejectCode.MISSING_FIELD
    assert "registered_at" in exc.value.reason


def test_registered_object_missing_is_rejected(raw: RawRecord) -> None:
    del raw["registered"]
    with pytest.raises(RecordRejected) as exc:
        clean_record(raw)
    assert exc.value.code == RejectCode.MISSING_FIELD


def test_registered_date_wrong_type_is_rejected(raw: RawRecord) -> None:
    raw["registered"]["date"] = 12345
    with pytest.raises(RecordRejected) as exc:
        clean_record(raw)
    assert exc.value.code == RejectCode.WRONG_TYPE
    assert "registered_at" in exc.value.reason


@pytest.mark.parametrize(
    "bad_date",
    [
        "yesterday",
        "",
        "   ",
        "2020-13-45T99:00:00Z",
        "2020-12-29T23:12:33",
        "2020-12-29",
    ],
)
def test_registered_date_invalid_is_rejected(raw: RawRecord, bad_date: str) -> None:
    raw["registered"]["date"] = bad_date
    with pytest.raises(RecordRejected) as exc:
        clean_record(raw)
    assert exc.value.code == RejectCode.INVALID_VALUE
    assert "registered_at" in exc.value.reason


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2020-12-29T23:12:33.098Z", "2020-12-29T23:12:33Z"),
        ("2020-12-29T23:12:33.999Z", "2020-12-29T23:12:33Z"),
        ("2020-12-29T23:12:33+02:00", "2020-12-29T21:12:33Z"),
        ("2020-12-29T23:12:33-05:00", "2020-12-30T04:12:33Z"),
        ("  2020-12-29T23:12:33Z ", "2020-12-29T23:12:33Z"),
    ],
)
def test_registered_date_is_converted_to_utc(raw: RawRecord, text: str, expected: str) -> None:
    raw["registered"]["date"] = text
    assert clean_record(raw).registered_at == expected
