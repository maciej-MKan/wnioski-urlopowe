"""Tests of working-day counting."""
from __future__ import annotations

from datetime import date

from app.domain.values import DateRange
from app.domain.working_days import is_working_day, nth_working_day_from_end, working_days


def test_working_day_and_weekend():
    assert is_working_day(date(2026, 8, 4)) is True   # Tuesday
    assert is_working_day(date(2026, 8, 8)) is False  # Saturday
    assert is_working_day(date(2026, 8, 9)) is False  # Sunday


def test_holiday_is_not_a_working_day():
    assert is_working_day(date(2026, 5, 1)) is False  # Labour Day (Friday)


def test_working_days_excludes_weekend():
    # Tue–Sat: Tue, Wed, Thu, Fri count = 4 (Saturday excluded)
    assert working_days(DateRange.from_strings("2026-08-04", "2026-08-08")) == 4


def test_working_days_excludes_holiday_in_range():
    # 1 May 2026 (Fri) is a holiday: Fri excluded, only Thursday 30.04 remains
    assert working_days(DateRange.from_strings("2026-04-30", "2026-05-01")) == 1


def test_working_days_full_week():
    # Mon–Fri without holidays = 5
    assert working_days(DateRange.from_strings("2026-08-10", "2026-08-14")) == 5


def test_working_days_weekend_range_is_zero():
    assert working_days(DateRange.from_strings("2026-08-08", "2026-08-09")) == 0


def test_working_days_invalid_range():
    assert working_days(DateRange.from_strings("2026-08-08", "")) is None
    assert working_days(DateRange.from_strings("2026-08-08", "2026-08-04")) is None


def test_working_days_across_year_boundary():
    # 29.12.2025 (Mon) .. 2.01.2026 (Fri): 1.01.2026 (Thu, New Year) is off.
    # Days: 29(Mon),30(Tue),31(Wed),1(Thu=holiday),2(Fri) => 29,30,31,2 = 4
    assert working_days(DateRange.from_strings("2025-12-29", "2026-01-02")) == 4


def test_nth_working_day_from_end():
    # 10.08 (Mon) .. 21.08.2026 (Fri) = 10 working days.
    period = DateRange.from_strings("2026-08-10", "2026-08-21")
    assert nth_working_day_from_end(period, 1) == date(2026, 8, 21)  # last working day
    assert nth_working_day_from_end(period, 2) == date(2026, 8, 20)


def test_nth_working_day_from_end_edge_cases():
    period = DateRange.from_strings("2026-08-10", "2026-08-21")
    assert nth_working_day_from_end(period, 0) is None
    assert nth_working_day_from_end(DateRange.from_strings("2026-08-10", ""), 1) is None
    # k larger than available working days clamps to the earliest working day.
    assert nth_working_day_from_end(period, 99) == date(2026, 8, 10)
