"""Computing the leave amount according to the type's unit.

Returns a `(days, hours)` pair to store on the record and use in the balance (Phase 4):
- a type counted in **working days** (annual leave) → count working days in the range,
- a type counted in **calendar days** (paternity) → count calendar days in the range,
- a type counted **in hours** → take the hour count from the `wymiar` field.

Art. 188 (child care) is dual-unit — "2 days or 16 hours" — so the record's unit is
decided by the `forma` field chosen by the employee, not the type declaration alone.
"""
from __future__ import annotations

from typing import Optional

from .leave_type import LeaveType
from .values import DateRange, Unit
from .working_days import working_days


def _number(value: object) -> Optional[float]:
    """Parses a number from a text field; None when empty or non-numeric."""
    text = str(value or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def compute_amount(leave_type: LeaveType, data: dict) -> tuple[Optional[float], Optional[float]]:
    """Returns `(days, hours)` for a record described by the application data."""
    period = DateRange.from_strings(data.get("data_od"), data.get("data_do"))

    # Art. 188: the unit depends on the employee's choice (`forma` field).
    forma = data.get("forma")
    if forma == "godziny":
        return None, _number(data.get("wymiar"))
    if forma == "dni":
        return _number(data.get("wymiar")), None

    if leave_type.unit == Unit.HOURS:
        return None, _number(data.get("wymiar"))

    if leave_type.unit == Unit.WORKING_DAYS:
        # The actual amount is working days in the range; the `liczba_dni` field is only a
        # description on the PDF and a fallback when dates are missing (0 working days is valid).
        wd = working_days(period)
        return (wd if wd is not None else _number(data.get("liczba_dni"))), None

    if leave_type.unit == Unit.CALENDAR_DAYS:
        cd = period.calendar_days()
        return (cd if cd is not None else _number(data.get("liczba_dni"))), None

    return None, None
