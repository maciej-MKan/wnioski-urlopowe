"""Tests of computing the leave usage balance."""
from __future__ import annotations

from app.domain.balance import compute_balance
from app.domain.entitlement import Entitlement
from app.domain.leave_record import LeaveRecord
from app.domain.leave_type import REGISTRY
from app.domain.values import DateRange, Pool, Status


def _rec(leave_type, status, pool=Pool.CURRENT, days=None, hours=None) -> LeaveRecord:
    return LeaveRecord(
        leave_type=leave_type, year=2026, data={"typ": leave_type}, period=DateRange(None, None),
        status=status, pool=pool, working_days=days, hours=hours,
    )


def _ent(leave_type, **kw) -> Entitlement:
    return Entitlement(year=2026, leave_type=leave_type, **kw)


def _by_label(items):
    return {item.label: item for item in items}


def test_annual_current_and_overdue():
    entitlements = {"wypoczynkowy": _ent("wypoczynkowy", limit_days=26, carried_over=5)}
    records = [
        _rec("wypoczynkowy", Status.APPROVED, Pool.CURRENT, days=4),
        _rec("wypoczynkowy", Status.PENDING, Pool.CURRENT, days=3),
        _rec("wypoczynkowy", Status.APPROVED, Pool.OVERDUE, days=2),
        _rec("wypoczynkowy", Status.REJECTED, Pool.CURRENT, days=10),  # skipped
    ]
    items = _by_label(compute_balance(REGISTRY, entitlements, records))

    current = items["Urlop wypoczynkowy (bieżący)"]
    assert current.used == 4 and current.planned == 3 and current.remaining == 22
    overdue = items["Urlop wypoczynkowy (zaległy)"]
    assert overdue.used == 2 and overdue.limit == 5 and overdue.remaining == 3


def test_inactive_type_skipped():
    entitlements = {"wypoczynkowy": _ent("wypoczynkowy", limit_days=26, carried_over=0)}
    labels = [item.label for item in compute_balance(REGISTRY, entitlements, [])]
    assert not any("ojcowski" in e.lower() for e in labels)
    assert not any("opieka" in e.lower() for e in labels)


def test_paternity_when_active():
    entitlements = {"ojcowski": _ent("ojcowski", active=True, limit_days=14)}
    records = [_rec("ojcowski", Status.APPROVED, days=14)]
    items = _by_label(compute_balance(REGISTRY, entitlements, records))
    assert items["Urlop ojcowski"].used == 14
    assert items["Urlop ojcowski"].remaining == 0


def test_child_care_single_pool_across_units():
    # Art. 188: jedna pula „2 dni albo 16 godzin" (1 dzień = 8 h) — formy się sumują (§20.1).
    entitlements = {"opieka": _ent("opieka", active=True, limit_days=2, limit_hours=16)}

    # Sam 1 dzień = 8 h → pula godzinowa spada do 8 (wcześniej błędnie zostawała pełna 16).
    items = _by_label(compute_balance(REGISTRY, entitlements, [_rec("opieka", Status.APPROVED, days=1)]))
    assert items["Opieka nad dzieckiem (dni)"].used == 1
    assert items["Opieka nad dzieckiem (dni)"].remaining == 1
    assert items["Opieka nad dzieckiem (godziny)"].used == 8
    assert items["Opieka nad dzieckiem (godziny)"].remaining == 8

    # 8 h + 1 dzień (=8 h) = pełna pula (2 dni / 16 h) — pozostało 0 na obu osiach.
    records = [_rec("opieka", Status.APPROVED, hours=8), _rec("opieka", Status.APPROVED, days=1)]
    items = _by_label(compute_balance(REGISTRY, entitlements, records))
    assert items["Opieka nad dzieckiem (dni)"].used == 2
    assert items["Opieka nad dzieckiem (dni)"].remaining == 0
    assert items["Opieka nad dzieckiem (godziny)"].used == 16
    assert items["Opieka nad dzieckiem (godziny)"].remaining == 0


def test_rejected_does_not_count():
    entitlements = {"wypoczynkowy": _ent("wypoczynkowy", limit_days=26, carried_over=0)}
    records = [_rec("wypoczynkowy", Status.REJECTED, days=5)]
    current = _by_label(compute_balance(REGISTRY, entitlements, records))["Urlop wypoczynkowy (bieżący)"]
    assert current.used == 0 and current.remaining == 26
