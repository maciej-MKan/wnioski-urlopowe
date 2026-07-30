"""Tests of the domain value objects."""
from __future__ import annotations

from datetime import date

import pytest

from app.domain.values import DateRange, Status, parse_date


@pytest.mark.parametrize(
    "given,expected",
    [
        ("2026-07-24", date(2026, 7, 24)),
        ("24.07.2026", date(2026, 7, 24)),
        ("24-07-2026", date(2026, 7, 24)),
    ],
)
def test_parse_date_recognizes_formats(given, expected):
    assert parse_date(given) == expected


@pytest.mark.parametrize("given", ["", None, "anything", "2026-13-40"])
def test_parse_date_returns_none_for_invalid(given):
    assert parse_date(given) is None


def test_range_calendar_days_includes_both_ends():
    assert DateRange.from_strings("2026-08-04", "2026-08-08").calendar_days() == 5


def test_range_single_day():
    assert DateRange.from_strings("2026-08-04", "2026-08-04").calendar_days() == 1


def test_reversed_range_is_invalid():
    period = DateRange.from_strings("2026-08-08", "2026-08-04")
    assert period.valid is False
    assert period.calendar_days() is None


def test_incomplete_range():
    assert DateRange.from_strings("2026-08-04", "").calendar_days() is None


def test_range_iso():
    period = DateRange.from_strings("2026-08-04", None)
    assert period.start_iso == "2026-08-04"
    assert period.end_iso is None


def test_range_is_value_object_compared_by_value():
    assert DateRange.from_strings("2026-08-04", "2026-08-08") == DateRange.from_strings(
        "2026-08-04", "2026-08-08"
    )


def test_status_is_string():
    assert Status.PENDING.value == "do_akceptacji"
