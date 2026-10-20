"""Turn raw API records into customers. Owner: Julian.

clean_record cleans one record. clean_records cleans a batch and rejects duplicates.
"""

import re
import uuid
from datetime import UTC, datetime

from customer_sync.contracts import CleanResult, Customer, RawRecord, RejectCode, Rejection

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RecordRejected(Exception):
    """One raw record failed validation. Internal to cleaning."""

    def __init__(self, code: RejectCode, reason: str) -> None:
        self.code = code
        self.reason = reason
        super().__init__(reason)


def _get(raw: RawRecord, *path: str) -> object:
    """Walk nested dicts. Return None if any level is absent or None."""
    current: object = raw
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _required_str(raw: RawRecord, *path: str, label: str) -> str:
    """Read a required string field: missing, wrong type, or blank is rejected."""
    value = _get(raw, *path)
    if value is None:
        raise RecordRejected(RejectCode.MISSING_FIELD, f"missing field: {label}")
    if not isinstance(value, str):
        raise RecordRejected(
            RejectCode.WRONG_TYPE, f"{label} must be str, got {type(value).__name__}"
        )
    value = value.strip()
    if not value:
        raise RecordRejected(RejectCode.INVALID_VALUE, f"{label} is blank")
    return value


def _optional_str(raw: RawRecord, *path: str, label: str, coerce_int: bool = False) -> str | None:
    """Read an optional string field. Absent or blank becomes None; wrong type is rejected."""
    value = _get(raw, *path)
    if value is None:
        return None
    if coerce_int and isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str):
        raise RecordRejected(
            RejectCode.WRONG_TYPE, f"{label} must be str, got {type(value).__name__}"
        )
    return value.strip() or None


def _is_canonical_uuid(text: str) -> bool:
    """True only for lowercase hyphenated UUIDs, e.g. 18d3d4f8-1b6c-480d-be6f-51de14bc1017."""
    try:
        return str(uuid.UUID(text)) == text
    except ValueError:
        return False


def _to_utc_text(text: str, label: str) -> str:
    """Parse an ISO 8601 timestamp with a timezone. Return UTC as YYYY-MM-DDTHH:MM:SSZ."""
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise RecordRejected(
            RejectCode.INVALID_VALUE, f"{label} is not an ISO 8601 timestamp: {text!r}"
        ) from None
    if parsed.tzinfo is None:
        raise RecordRejected(RejectCode.INVALID_VALUE, f"{label} has no timezone: {text!r}")
    try:
        utc = parsed.astimezone(UTC)
    except OverflowError:
        raise RecordRejected(
            RejectCode.INVALID_VALUE, f"{label} is out of range: {text!r}"
        ) from None
    return utc.replace(microsecond=0, tzinfo=None).isoformat() + "Z"


def clean_record(raw: RawRecord) -> Customer:
    """Turn one raw API record into a Customer. Raises RecordRejected(code, reason)."""
    uuid_text = _required_str(raw, "login", "uuid", label="uuid").lower()
    if not _is_canonical_uuid(uuid_text):
        raise RecordRejected(RejectCode.INVALID_VALUE, f"invalid uuid: {uuid_text!r}")
    first_name = _required_str(raw, "name", "first", label="first_name")
    last_name = _required_str(raw, "name", "last", label="last_name")
    email = _required_str(raw, "email", label="email").lower()
    if not _EMAIL_RE.match(email):
        raise RecordRejected(RejectCode.INVALID_VALUE, f"invalid email: {email!r}")
    registered_text = _required_str(raw, "registered", "date", label="registered_at")
    registered_at = _to_utc_text(registered_text, "registered_at")
    phone = _optional_str(raw, "phone", label="phone", coerce_int=True)
    city = _optional_str(raw, "location", "city", label="city")
    country = _optional_str(raw, "location", "country", label="country")

    return Customer(
        uuid=uuid_text,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        city=city,
        country=country,
        registered_at=registered_at,
    )


def clean_records(raws: list[RawRecord]) -> CleanResult:
    """Clean a batch. Duplicate uuid or email in the batch is rejected."""
    raise NotImplementedError
