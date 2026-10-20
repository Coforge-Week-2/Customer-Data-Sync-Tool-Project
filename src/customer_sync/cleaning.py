"""Turn raw API records into customers. Owner: Julian.

Stub only. clean_record and clean_records raise NotImplementedError.
"""

import re
from datetime import UTC, datetime

from customer_sync.contracts import CleanResult, Customer, RawRecord, RejectCode

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


def clean_record(raw: RawRecord) -> Customer:
    """Turn one raw API record into a Customer. Raises RecordRejected(code, reason)."""
    registered = datetime.fromisoformat(raw["registered"]["date"])
    first_name = _required_str(raw, "name", "first", label="first_name")
    last_name = _required_str(raw, "name", "last", label="last_name")
    email = _required_str(raw, "email", label="email").lower()
    if not _EMAIL_RE.match(email):
        raise RecordRejected(RejectCode.INVALID_VALUE, f"invalid email: {email!r}")

    return Customer(
        uuid=raw["login"]["uuid"],
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=raw["phone"],
        city=raw["location"]["city"],
        country=raw["location"]["country"],
        registered_at=registered.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def clean_records(raws: list[RawRecord]) -> CleanResult:
    """Clean a batch. Duplicate uuid or email in the batch is rejected."""
    raise NotImplementedError
