"""Tests of the Polish holiday calendar."""
from __future__ import annotations

from datetime import date

import pytest

from app.domain.holidays import easter, polish_holidays, polish_holidays_named, saturday_holidays


@pytest.mark.parametrize(
    "year,expected",
    [
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
    ],
)
def test_easter_known_dates(year, expected):
    assert easter(year) == expected


def test_fixed_holidays_present():
    s = polish_holidays(2026)
    for d in [date(2026, 1, 1), date(2026, 5, 1), date(2026, 5, 3), date(2026, 11, 11),
              date(2026, 12, 25), date(2026, 12, 26)]:
        assert d in s


def test_movable_holidays_2026():
    s = polish_holidays(2026)
    assert date(2026, 4, 6) in s  # Easter Monday
    assert date(2026, 6, 4) in s  # Corpus Christi (Easter + 60 days, Thursday)


def test_christmas_eve_off_since_2025():
    assert date(2025, 12, 24) in polish_holidays(2025)
    assert date(2026, 12, 24) in polish_holidays(2026)


def test_christmas_eve_not_off_before_2025():
    assert date(2024, 12, 24) not in polish_holidays(2024)


def test_corpus_christi_is_thursday():
    from datetime import timedelta

    assert (easter(2026) + timedelta(days=60)).weekday() == 3  # Thursday


def test_named_matches_set():
    named = polish_holidays_named(2026)
    assert set(named) == set(polish_holidays(2026))


def test_named_have_names():
    named = polish_holidays_named(2026)
    assert named[date(2026, 1, 1)] == "Nowy Rok"
    assert named[date(2026, 4, 6)] == "Poniedziałek Wielkanocny"
    assert named[date(2026, 6, 4)] == "Boże Ciało"


def test_saturday_holidays_2025():
    # In 2025 both 3 May (Constitution Day) and 1 Nov (All Saints) fall on Saturday.
    sat = saturday_holidays(2025)
    assert date(2025, 5, 3) in sat
    assert date(2025, 11, 1) in sat


def test_saturday_holidays_are_saturdays_and_holidays():
    for year in (2024, 2025, 2026, 2027):
        sat = saturday_holidays(year)
        assert sat == sorted(sat)  # ascending
        for d in sat:
            assert d.weekday() == 5  # Saturday
            assert d in polish_holidays(year)
