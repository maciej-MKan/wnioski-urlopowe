"""Tests of computing the leave amount by the type's unit."""
from __future__ import annotations

from app.domain.leave_amount import compute_amount
from app.domain.leave_type import REGISTRY


def _amount(payload):
    data = REGISTRY.validate(payload)
    return compute_amount(REGISTRY.required(data["typ"]), data)


def test_annual_leave_counts_working_days_from_range():
    # 04–08.08.2026 = 4 working days (Saturday excluded), regardless of entered liczba_dni
    days, hours = _amount({"typ": "wypoczynkowy", "data_od": "2026-08-04",
                           "data_do": "2026-08-08", "liczba_dni": "5"})
    assert days == 4
    assert hours is None


def test_annual_leave_without_dates_uses_day_count():
    days, hours = _amount({"typ": "wypoczynkowy", "liczba_dni": "3"})
    assert days == 3
    assert hours is None


def test_paternity_counts_calendar_days():
    # 2 weeks calendar-wise: 01–14.06 = 14 days
    days, hours = _amount({"typ": "ojcowski", "data_od": "2026-06-01",
                           "data_do": "2026-06-14", "wymiar": "2 tygodnie"})
    assert days == 14
    assert hours is None


def test_child_care_hours():
    days, hours = _amount({"typ": "opieka", "forma": "godziny", "wymiar": "8"})
    assert days is None
    assert hours == 8


def test_child_care_days():
    days, hours = _amount({"typ": "opieka", "forma": "dni", "wymiar": "2"})
    assert days == 2
    assert hours is None


def test_child_care_fractional_hours():
    _, hours = _amount({"typ": "opieka", "forma": "godziny", "wymiar": "1,5"})
    assert hours == 1.5
