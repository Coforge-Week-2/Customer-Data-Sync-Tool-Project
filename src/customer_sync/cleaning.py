"""Turn raw API records into customers. Owner: Julian.

Stub only. clean_record and clean_records raise NotImplementedError.
"""

from customer_sync.contracts import CleanResult, Customer, RawRecord, RejectCode


class RecordRejected(Exception):
    """One raw record failed validation. Internal to cleaning."""

    def __init__(self, code: RejectCode, reason: str) -> None:
        self.code = code
        self.reason = reason
        super().__init__(reason)


def clean_record(raw: RawRecord) -> Customer:
    """Turn one raw API record into a Customer. Raises RecordRejected(code, reason)."""
    raise NotImplementedError


def clean_records(raws: list[RawRecord]) -> CleanResult:
    """Clean a batch. Duplicate uuid or email in the batch is rejected."""
    raise NotImplementedError
