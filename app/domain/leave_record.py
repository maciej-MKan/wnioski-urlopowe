"""`LeaveRecord` aggregate — the consistency root of a single leave.

Gathers state and transition rules (status, period correction with an audit trail). The
methods enforce domain invariants instead of allowing arbitrary field setting from
outside. Some behaviors (approval/rejection, correction) only fed endpoints in Phase 5 — we
modeled them earlier because they belong to the domain and are testable in isolation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date

from .errors import InvalidCorrection
from .values import DateRange, Pool, Source, Status, parse_date


def _year_from_data(data: dict) -> int:
    """Calendar year of the leave: from `data_od`, falling back to document `data` / today."""
    for key in ("data_od", "data"):
        d = parse_date(data.get(key, ""))
        if d:
            return d.year
    return date.today().year


def _pool_from_data(data: dict) -> Pool:
    """Which pool the leave is drawn from (§16.3).

    Driven by `rok_rozliczenia` (settlement year): a year earlier than the leave's year means
    it is charged to the overdue pool; the leave's own year means the current pool. Falls back
    to the legacy `za_okres` field for backward-compatible payloads.
    """
    settlement = str(data.get("rok_rozliczenia", "")).strip()
    if settlement.isdigit():
        return Pool.OVERDUE if int(settlement) < _year_from_data(data) else Pool.CURRENT
    return Pool.OVERDUE if data.get("za_okres") == "zalegly" else Pool.CURRENT


@dataclass
class LeaveRecord:
    """A stored leave — from a PDF application or (since Phase 5) added manually."""

    leave_type: str
    year: int
    data: dict  # normalized application data (per type) — source to rebuild the document
    period: DateRange
    status: Status = Status.PENDING
    source: Source = Source.APPLICATION
    pool: Pool = Pool.CURRENT  # "za okres"; the pool choice was added in Phase 4
    working_days: float | None = None  # filled in Phase 2
    hours: float | None = None  # filled in Phase 2
    # Attachment (§13.1): for applications this is the generated PDF, for manual records —
    # an attached scan/certificate (PDF or JPG). `None` when the record has no file.
    attachment_mime: str | None = None
    attachment_name: str | None = None
    correction_reason: str | None = None
    original_period: DateRange | None = None  # audit trail before correction
    created_at: str = ""
    updated_at: str = ""
    id: int | None = None
    # Transient field: PDF bytes to persist on `save`. Not part of the record identity.
    document: bytes | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_application(
        cls,
        data: dict,
        now: str,
        working_days: float | None = None,
        hours: float | None = None,
        document: bytes | None = None,
    ) -> "LeaveRecord":
        """Creates a new record from generated application data (status `pending`).

        The amount (`working_days`/`hours`) is computed by the application layer via
        `compute_amount` and passed here — the aggregate knows neither the working-day rules
        nor the type registry.
        """
        return cls(
            leave_type=data["typ"],
            year=_year_from_data(data),
            data=dict(data),
            period=DateRange.from_strings(data.get("data_od"), data.get("data_do")),
            source=Source.APPLICATION,
            status=Status.PENDING,
            pool=_pool_from_data(data),
            working_days=working_days,
            hours=hours,
            created_at=now,
            updated_at=now,
            document=document,
        )

    @property
    def content_hash(self) -> str:
        """A stable fingerprint of the application content — identity of "the same" leave.

        Enables idempotent saving: regenerating an identical PDF refreshes the existing
        record instead of creating a duplicate.
        """
        canonical = json.dumps(self.data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def manual(
        cls,
        data: dict,
        now: str,
        status: Status = Status.APPROVED,
        working_days: float | None = None,
        hours: float | None = None,
    ) -> "LeaveRecord":
        """Creates a record of leave taken outside the application (`source=manual`, no PDF).

        Approved right away by default — it concerns leave that already happened (plan §8.2).
        """
        return cls(
            leave_type=data["typ"],
            year=_year_from_data(data),
            data=dict(data),
            period=DateRange.from_strings(data.get("data_od"), data.get("data_do")),
            source=Source.MANUAL,
            status=status,
            pool=_pool_from_data(data),
            working_days=working_days,
            hours=hours,
            created_at=now,
            updated_at=now,
        )

    @property
    def counts_as_used(self) -> bool:
        """Whether the record counts as used leave in the balance (Phase 4)."""
        return self.status == Status.APPROVED

    def mark(self, status: Status, now: str) -> None:
        """Sets the record status (approval / rejection / back to pending)."""
        self.status = status
        self.updated_at = now

    def approve(self, now: str) -> None:
        self.mark(Status.APPROVED, now)

    def reject(self, now: str) -> None:
        self.mark(Status.REJECTED, now)

    def correct_period(self, new: DateRange, reason: str, now: str) -> None:
        """Changes the leave period (e.g. shortened by sick leave), keeping the original for audit."""
        if not reason.strip():
            raise InvalidCorrection("A period correction requires a reason.")
        if self.original_period is None:
            self.original_period = self.period
        self.period = new
        self.correction_reason = reason.strip()
        self.updated_at = now
