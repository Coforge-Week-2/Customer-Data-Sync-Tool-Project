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


def clean_record(raw: RawRecord) -> Customer:
    """Turn one raw API record into a Customer. Raises RecordRejected(code, reason)."""
    registered = datetime.fromisoformat(raw["registered"]["date"])

    email = raw.get("email")
    if email is None:
        raise RecordRejected(RejectCode.MISSING_FIELD, "missing field: email")
    if not isinstance(email, str):
        raise RecordRejected(
            RejectCode.WRONG_TYPE, f"email must be str, got {type(email).__name__}"
        )
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise RecordRejected(RejectCode.INVALID_VALUE, f"invalid email: {email!r}")

    return Customer(
        uuid=raw["login"]["uuid"],
        first_name=raw["name"]["first"],
        last_name=raw["name"]["last"],
        email=email,
        phone=raw["phone"],
        city=raw["location"]["city"],
        country=raw["location"]["country"],
        registered_at=registered.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def clean_records(raws: list[RawRecord]) -> CleanResult:
    """Clean a batch. Duplicate uuid or email in the batch is rejected."""
    raise NotImplementedError
