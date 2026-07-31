"""Leave usage balance — limit vs used vs remaining (plan §7).

Status rules: `approved` counts as **used**, `pending` as **planned** (shown separately),
`rejected` ignored. Annual leave splits into a current and an overdue pool by the record's
"za okres" field. Child care (art. 188) is dual-unit ("2 days or 16 hours"), so we show two
axes: days and hours. Balance labels stay Polish (user-facing).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .entitlement import Entitlement
from .leave_record import LeaveRecord
from .leave_type import LeaveTypeRegistry
from .values import Pool, Status, Unit


#: Reserved pseudo-type id for the "days off for Saturday holidays" balance line (§14).
WEEKEND_OFF_ID = "wolne_za_swieta"


#: Polish month names (nominative) for the §16.1 per-month balance labels.
_MONTHS_NOM = [
    "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
    "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień",
]


@dataclass(frozen=True)
class BalanceItem:
    leave_type: str
    label: str
    unit: str  # "dni" | "godziny" — for display
    limit: Optional[float]
    used: float  # approved records
    planned: float  # pending records
    remaining: Optional[float]  # limit - used; None when no limit
    short_term: bool = False  # highlighted: shorter validity (use within the settlement period)
    month: Optional[int] = None  # §16.1: month (1–12) the short-term line settles in


def weekend_holiday_items(year: int, saturday_dates, records: list["LeaveRecord"]) -> list[BalanceItem]:
    """Highlighted balance lines for days off owed for Saturday holidays (§14/§15/§16.1).

    One line **per month** that has a Saturday holiday, because such a day off must be taken
    within the same calendar month as the holiday (art. 130 § 2 K.p.) — a shorter validity
    than overdue annual leave. `limit` is the number of Saturday holidays in that month;
    `used`/`planned` come from `wolne_za_swieta` records dated in that month.
    """
    recs = [r for r in records if r.leave_type == WEEKEND_OFF_ID]
    per_month: dict[int, int] = {}
    for d in saturday_dates:
        per_month[d.month] = per_month.get(d.month, 0) + 1

    items: list[BalanceItem] = []
    for month in sorted(per_month):
        count = per_month[month]
        month_recs = [r for r in recs if r.period.start is not None and r.period.start.month == month]
        used = sum(r.working_days or 0 for r in month_recs if r.status == Status.APPROVED)
        planned = sum(r.working_days or 0 for r in month_recs if r.status == Status.PENDING)
        items.append(BalanceItem(
            leave_type=WEEKEND_OFF_ID,
            label=f"Dni wolne za święto ({_MONTHS_NOM[month - 1]} {year})",
            unit="dni",
            limit=float(count),
            used=used,
            planned=planned,
            remaining=float(count) - used,
            short_term=True,
            month=month,
        ))
    return items


def _sum(records: list[LeaveRecord], attribute: str, status: Status) -> float:
    return sum(getattr(r, attribute) or 0 for r in records if r.status == status)


def _item(leave_type, label, unit, limit, records, attribute) -> BalanceItem:
    used = _sum(records, attribute, Status.APPROVED)
    planned = _sum(records, attribute, Status.PENDING)
    remaining = (limit - used) if limit is not None else None
    return BalanceItem(leave_type, label, unit, limit, used, planned, remaining)


def _dual_unit_items(leave_type, ent, records: list[LeaveRecord]) -> list[BalanceItem]:
    """Child care (art. 188): one pool shown on two axes (days, hours).

    Usage from day-form and hour-form records shares a single pool: a day counts as
    `hours_per_day` hours (= limit_hours / limit_days, i.e. 8). We settle in hours and derive
    the days axis from the same total, so any record decrements both axes consistently.
    """
    hours_per_day = (ent.limit_hours / ent.limit_days) if (ent.limit_days and ent.limit_hours) else 8.0

    def hours_for(status: Status) -> float:
        total = 0.0
        for r in records:
            if r.status != status:
                continue
            if r.hours is not None:
                total += r.hours
            elif r.working_days is not None:
                total += r.working_days * hours_per_day
        return total

    used_h = hours_for(Status.APPROVED)
    planned_h = hours_for(Status.PENDING)

    def line(label: str, unit: str, limit, used: float, planned: float) -> BalanceItem:
        return BalanceItem(leave_type.id, label, unit, limit, used, planned,
                           (limit - used) if limit is not None else None)

    return [
        line(f"{leave_type.name} (dni)", "dni", ent.limit_days, used_h / hours_per_day, planned_h / hours_per_day),
        line(f"{leave_type.name} (godziny)", "godziny", ent.limit_hours, used_h, planned_h),
    ]


def compute_balance(
    registry: LeaveTypeRegistry,
    entitlements: dict[str, Entitlement],
    records: list[LeaveRecord],
) -> list[BalanceItem]:
    """Balance items for active types; types unchecked in Settings are skipped."""
    items: list[BalanceItem] = []
    for leave_type in registry.all():
        if leave_type.id == WEEKEND_OFF_ID:
            continue  # §15: handled separately as a highlighted short-term line
        ent = entitlements.get(leave_type.id)
        if ent is None or not ent.active:
            continue
        # Rejected records do not affect the balance.
        recs = [r for r in records if r.leave_type == leave_type.id and r.status != Status.REJECTED]

        if leave_type.has_overdue:
            current = [r for r in recs if r.pool == Pool.CURRENT]
            overdue = [r for r in recs if r.pool == Pool.OVERDUE]
            items.append(_item(leave_type.id, f"{leave_type.name} (bieżący)", "dni", ent.limit_days, current, "working_days"))
            items.append(
                _item(leave_type.id, f"{leave_type.name} (zaległy)", "dni", ent.carried_over, overdue, "working_days")
            )
        elif leave_type.default_limit_days is not None and leave_type.default_limit_hours is not None:
            # Dual-unit type (art. 188): ONE pool "2 days OR 16 hours". A day and hours draw from
            # the same pool, so convert every record to hours (1 day = limit_hours/limit_days h),
            # settle in hours, then present both axes (days, hours) derived from that single total.
            items.extend(_dual_unit_items(leave_type, ent, recs))
        elif leave_type.unit == Unit.HOURS:
            items.append(_item(leave_type.id, leave_type.name, "godziny", ent.limit_hours, recs, "hours"))
        else:
            items.append(_item(leave_type.id, leave_type.name, "dni", ent.limit_days, recs, "working_days"))
    return items
