"""Value objects and enumerations of the domain.

A value object is an immutable value without identity — two equal date ranges are
indistinguishable. Enums name finite sets of domain concepts (record status, source,
pool, unit). The enum *values* stay Polish because they are the wire/storage contract
(API, SQLite); only the member identifiers are English.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class Status(str, Enum):
    """Life cycle of a leave record."""

    PENDING = "do_akceptacji"
    APPROVED = "zaakceptowany"
    REJECTED = "odrzucony"


class Source(str, Enum):
    """Where the record comes from."""

    APPLICATION = "wniosek"  # from a generated PDF
    MANUAL = "reczny"  # leave taken outside the application (Phase 5)


class Pool(str, Enum):
    """Which pool the leave is drawn from (for types with an overdue pool)."""

    CURRENT = "biezacy"
    OVERDUE = "zalegly"


class Unit(str, Enum):
    """The unit a given leave type's amount is measured in."""

    WORKING_DAYS = "dni_robocze"
    CALENDAR_DAYS = "dni_kalendarzowe"
    HOURS = "godziny"


def parse_date(value: str | None) -> date | None:
    """Recognizes a date in 'YYYY-MM-DD', 'DD.MM.YYYY', 'DD-MM-YYYY' formats.

    Returns None for an empty or unrecognized value — the form is often incomplete.
    """
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class DateRange:
    """A start–end range. Value object: immutable, compared by value.

    Deliberately tolerant of incomplete data (a form being filled in): a missing or
    reversed bound does not raise — `calendar_days()` returns None then.
    """

    start: date | None
    end: date | None

    @classmethod
    def from_strings(cls, start: str | None, end: str | None) -> "DateRange":
        return cls(parse_date(start), parse_date(end))

    @property
    def complete(self) -> bool:
        return self.start is not None and self.end is not None

    @property
    def valid(self) -> bool:
        """Complete and not reversed (end >= start)."""
        return self.complete and self.end >= self.start  # type: ignore[operator]

    def calendar_days(self) -> int | None:
        """Number of calendar days inclusive of both ends; None when the range is invalid."""
        if not self.valid:
            return None
        return (self.end - self.start).days + 1  # type: ignore[operator]

    @property
    def start_iso(self) -> str | None:
        return self.start.isoformat() if self.start else None

    @property
    def end_iso(self) -> str | None:
        return self.end.isoformat() if self.end else None
