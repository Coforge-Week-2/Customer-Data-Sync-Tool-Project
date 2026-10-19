"""Shared types for the sync pipeline. Frozen after Phase 0.

Changes follow PLAN.md §2.6: a ticket, then a PR labeled contract-change
approved by all four owners.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

RawRecord = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Customer:
    uuid: str
    first_name: str
    last_name: str
    email: str
    phone: str | None
    city: str | None
    country: str | None
    registered_at: str


class RejectCode(StrEnum):
    MISSING_FIELD = "missing_field"
    WRONG_TYPE = "wrong_type"
    INVALID_VALUE = "invalid_value"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class Rejection:
    index: int
    uuid: str | None
    code: RejectCode
    reason: str
    raw: RawRecord


@dataclass(frozen=True, slots=True)
class CleanResult:
    accepted: list[Customer]
    rejected: list[Rejection]


@dataclass(frozen=True, slots=True)
class UpsertCounts:
    added: int
    updated: int
    unchanged: int


@dataclass(frozen=True, slots=True)
class SyncSummary:
    added: int
    updated: int
    unchanged: int
    rejected: int
    rejections: list[Rejection] = field(default_factory=list)


class RecordSource(Protocol):
    """API client and file source both implement this."""

    def fetch_records(self) -> list[RawRecord]: ...


class CustomerRepository(Protocol):
    """SQLite store implements this. CLI tests use a fake."""

    def upsert_many(self, customers: Iterable[Customer]) -> UpsertCounts: ...


class SyncError(Exception):
    """Base error for a failed sync."""


class ApiError(SyncError):
    """Retries exhausted or the API response is unrecoverable."""


class SourceFileError(SyncError):
    """--from-file path is missing, unreadable, or the wrong shape."""


class StorageError(SyncError):
    """The local database could not be read or written."""
