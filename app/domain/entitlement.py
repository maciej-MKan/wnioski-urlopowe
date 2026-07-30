"""Entitlement — the leave amount due in a given year.

Configured manually in the Settings tab (plan §3.2, §8): for annual leave the number of
current and overdue days, for other types — whether they are due at all. A single type's
limits come from the descriptor (`LeaveType`), so the "is due" checkbox is enough for
types with a fixed amount.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Entitlement:
    year: int
    leave_type: str  # leave type id (wire value, stays Polish)
    active: bool = True  # whether to show in the given year's balance
    limit_days: Optional[float] = None
    limit_hours: Optional[float] = None
    carried_over: Optional[float] = None  # overdue (days) brought into this year
    notes: str = ""
