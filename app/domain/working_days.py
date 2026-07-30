"""Counting working days with public holidays taken into account.

A working day = Monday–Friday that is not a statutory day off (`holidays`). This realizes
the "real trap" from plan §5: annual leave is drawn from the pool in working days, not
calendar days.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

from .holidays import polish_holidays
from .values import DateRange

# The holiday provider is injectable so tests can supply their own calendar.
HolidayProvider = Callable[[int], "frozenset[date]"]


def is_working_day(d: date, holidays: HolidayProvider = polish_holidays) -> bool:
    """Whether the given date is a working day (Mon–Fri and not a holiday)."""
    return d.weekday() < 5 and d not in holidays(d.year)


def working_days(period: DateRange, holidays: HolidayProvider = polish_holidays) -> int | None:
    """Number of working days in the range (inclusive of both ends); None when invalid."""
    if not period.valid:
        return None
    assert period.start is not None and period.end is not None  # guaranteed by `valid`
    count = 0
    day = period.start
    while day <= period.end:
        if is_working_day(day, holidays):
            count += 1
        day += timedelta(days=1)
    return count


def nth_working_day_from_end(period: DateRange, k: int, holidays: HolidayProvider = polish_holidays) -> date | None:
    """Date of the k-th working day counting backwards from the range end (§15 split).

    Used to carve the trailing `k` working days of an annual-leave range into a separate
    "day off for a Saturday holiday" sub-period. Returns None for `k <= 0` or an invalid
    range; clamps to the earliest working day when `k` exceeds the working days available.
    """
    if k <= 0 or not period.valid:
        return None
    assert period.start is not None and period.end is not None
    seen = 0
    day = period.end
    result = period.start
    while day >= period.start:
        if is_working_day(day, holidays):
            seen += 1
            result = day
            if seen == k:
                return day
        day -= timedelta(days=1)
    return result
