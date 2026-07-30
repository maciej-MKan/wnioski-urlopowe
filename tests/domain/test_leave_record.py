"""Tests of the LeaveRecord aggregate — factory, status transitions, correction, identity."""
from __future__ import annotations

import pytest

from app.domain.errors import InvalidCorrection
from app.domain.leave_record import LeaveRecord
from app.domain.values import DateRange, Pool, Source, Status

NOW = "2026-07-24T10:00:00"


def _record(**overrides) -> LeaveRecord:
    data = {"typ": "wypoczynkowy", "data_od": "2026-08-04", "data_do": "2026-08-08"}
    data.update(overrides)
    return LeaveRecord.from_application(data, now=NOW)


def test_from_application_sets_initial_state():
    r = _record()
    assert r.status == Status.PENDING
    assert r.source == Source.APPLICATION
    assert r.year == 2026
    assert r.period == DateRange.from_strings("2026-08-04", "2026-08-08")
    assert r.created_at == NOW == r.updated_at


def test_current_pool_by_default():
    assert _record().pool == Pool.CURRENT


def test_overdue_pool_from_earlier_settlement_year():
    # §16.3: settlement year < leave year → overdue pool.
    r = LeaveRecord.from_application(
        {"typ": "wypoczynkowy", "data_od": "2026-08-04", "rok_rozliczenia": "2025"}, now=NOW)
    assert r.pool == Pool.OVERDUE


def test_current_pool_when_settlement_year_matches():
    r = LeaveRecord.from_application(
        {"typ": "wypoczynkowy", "data_od": "2026-08-04", "rok_rozliczenia": "2026"}, now=NOW)
    assert r.pool == Pool.CURRENT


def test_overdue_pool_legacy_za_okres_fallback():
    # Backward compatibility for old payloads without `rok_rozliczenia`.
    r = LeaveRecord.from_application({"typ": "wypoczynkowy", "za_okres": "zalegly"}, now=NOW)
    assert r.pool == Pool.OVERDUE


def test_year_from_document_date_when_no_data_od():
    r = LeaveRecord.from_application({"typ": "opieka", "data": "2025-03-01"}, now=NOW)
    assert r.year == 2025


def test_content_hash_stable_and_distinguishing():
    assert _record().content_hash == _record().content_hash
    assert _record().content_hash != _record(data_do="2026-08-09").content_hash


def test_approve_changes_status_and_marker():
    r = _record()
    r.approve("2026-07-25T09:00:00")
    assert r.status == Status.APPROVED
    assert r.updated_at == "2026-07-25T09:00:00"
    assert r.counts_as_used is True


def test_reject_does_not_count_as_used():
    r = _record()
    r.reject(NOW)
    assert r.status == Status.REJECTED
    assert r.counts_as_used is False


def test_correct_period_keeps_original_range():
    r = _record()
    new = DateRange.from_strings("2026-08-04", "2026-08-05")
    r.correct_period(new, reason="L4", now="2026-08-06T08:00:00")
    assert r.period == new
    assert r.original_period == DateRange.from_strings("2026-08-04", "2026-08-08")
    assert r.correction_reason == "L4"


def test_second_correction_does_not_overwrite_original():
    r = _record()
    r.correct_period(DateRange.from_strings("2026-08-04", "2026-08-06"), "L4", NOW)
    r.correct_period(DateRange.from_strings("2026-08-04", "2026-08-05"), "another L4", NOW)
    assert r.original_period == DateRange.from_strings("2026-08-04", "2026-08-08")


def test_correction_without_reason_raises():
    with pytest.raises(InvalidCorrection):
        _record().correct_period(DateRange.from_strings("2026-08-04", "2026-08-05"), "  ", NOW)


def test_manual_has_manual_source_and_approved_by_default():
    r = LeaveRecord.manual({"typ": "wypoczynkowy", "data_od": "2026-05-04", "data_do": "2026-05-05"}, now=NOW)
    assert r.source == Source.MANUAL
    assert r.status == Status.APPROVED


def test_mark_sets_any_status():
    r = _record()
    r.mark(Status.REJECTED, "2026-07-25T10:00:00")
    assert r.status == Status.REJECTED
    r.mark(Status.PENDING, "2026-07-26T10:00:00")
    assert r.status == Status.PENDING
