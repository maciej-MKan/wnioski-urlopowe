"""Tests of the application service on doubles (without SQLite/WeasyPrint)."""
from __future__ import annotations

import pytest

from app.domain.errors import UnknownLeaveType
from app.domain.values import Status

ANNUAL = {
    "typ": "wypoczynkowy",
    "imie_nazwisko": "Jan Kowalski",
    "data_od": "2026-08-04",
    "data_do": "2026-08-08",
}


def test_preview_returns_html_from_generator(service):
    html = service.preview(ANNUAL)
    assert "wypoczynkowy" in html


def test_preview_unknown_type_raises(service):
    with pytest.raises(UnknownLeaveType):
        service.preview({"typ": "nieistnieje"})


def test_prepare_returns_pdf_and_name(service):
    result = service.prepare(ANNUAL)
    assert result.pdf.startswith(b"%PDF")
    assert result.file_name == "wniosek_wypoczynkowy_Jan_Kowalski_2026-08-04.pdf"


def test_prepare_does_not_save(service):
    service.prepare(ANNUAL)
    assert service.list_records() == []


def test_save_creates_record(service):
    result = service.prepare(ANNUAL)
    record = service.save(result.data, result.pdf)
    assert record.id is not None
    assert record.status == Status.PENDING
    assert len(service.list_records()) == 1


def test_save_computes_working_days(service):
    # 04–08.08.2026 = 4 working days (Saturday out of the pool)
    result = service.prepare(ANNUAL)
    record = service.save(result.data, result.pdf)
    assert record.working_days == 4
    assert record.hours is None


def test_recompute_amounts_fills_empty(service, repo):
    from app.domain.leave_record import LeaveRecord

    # A record "from before Phase 2" — without a computed amount.
    data = service.registry.validate(ANNUAL)
    repo.save(LeaveRecord.from_application(data, now="2026-01-01T00:00:00"))
    assert repo.list()[0].working_days is None

    assert service.recompute_amounts() == 1
    assert repo.list()[0].working_days == 4
    # Recomputing again changes nothing (idempotent).
    assert service.recompute_amounts() == 0


def test_save_is_idempotent_by_content(service):
    p = service.prepare(ANNUAL)
    r1 = service.save(p.data, p.pdf)
    r2 = service.save(p.data, p.pdf)
    assert r1.id == r2.id
    assert len(service.list_records()) == 1


def test_record_pdf_returns_saved_bytes(service):
    p = service.prepare(ANNUAL)
    record = service.save(p.data, p.pdf)
    assert service.record_pdf(record.id) == p.pdf


def _pat(data_od, data_do, child="2026-01-10"):
    return {
        "typ": "ojcowski",
        "imie_nazwisko": "Jan Kowalski",
        "dziecko_imie_nazwisko": "Dziecko Kowalski",
        "dziecko_data_urodzenia": child,
        "wymiar": "2 tygodnie",
        "data_od": data_od,
        "data_do": data_do,
    }


def test_paternity_part_shorter_than_week_rejected(service):
    with pytest.raises(ValueError):
        service.add_manual(_pat("2026-03-02", "2026-03-07"))  # 6 dni kalendarzowych


def test_paternity_week_part_accepted(service):
    service.add_manual(_pat("2026-03-02", "2026-03-08"))  # dokładnie 7 dni
    assert len(service.list_records()) == 1


def test_paternity_total_over_two_weeks_rejected(service):
    service.add_manual(_pat("2026-03-02", "2026-03-08"))  # 7
    service.add_manual(_pat("2026-04-06", "2026-04-12"))  # +7 = 14 (OK)
    with pytest.raises(ValueError):
        service.add_manual(_pat("2026-05-04", "2026-05-10"))  # +7 = 21 > 14


def test_paternity_rules_are_per_child(service):
    service.add_manual(_pat("2026-03-02", "2026-03-15", child="2026-01-10"))  # 14 dni, dziecko A
    service.add_manual(_pat("2026-04-06", "2026-04-19", child="2026-06-20"))  # 14 dni, dziecko B — OK
    assert len(service.list_records()) == 2


def test_paternity_correction_cannot_bypass_min_part(service):
    rec = service.add_manual(_pat("2026-03-02", "2026-03-08"))  # 7 dni
    with pytest.raises(ValueError):
        service.correct_period(rec.id, "2026-03-02", "2026-03-06", "skrócenie")  # 5 dni — furtka zamknięta


def test_overlap_same_type_rejected(service):
    service.add_manual({"typ": "wypoczynkowy", "data_od": "2026-06-01", "data_do": "2026-06-05"})
    with pytest.raises(ValueError):
        service.add_manual({"typ": "wypoczynkowy", "data_od": "2026-06-04", "data_do": "2026-06-08"})


def test_overlap_across_types_rejected(service):
    service.add_manual({"typ": "wypoczynkowy", "data_od": "2026-06-01", "data_do": "2026-06-05"})
    with pytest.raises(ValueError):  # opieka w dniu zajętym przez urlop — jeden urlop na dzień
        service.add_manual({"typ": "opieka", "forma": "dni", "wymiar": "1",
                            "data_od": "2026-06-03", "data_do": "2026-06-03"})


def test_adjacent_periods_allowed(service):
    service.add_manual({"typ": "wypoczynkowy", "data_od": "2026-06-01", "data_do": "2026-06-05"})
    service.add_manual({"typ": "wypoczynkowy", "data_od": "2026-06-06", "data_do": "2026-06-10"})  # przylega
    assert len(service.list_records()) == 2


def test_correction_into_overlap_rejected(service):
    service.add_manual({"typ": "wypoczynkowy", "data_od": "2026-06-01", "data_do": "2026-06-05"})
    rec = service.add_manual({"typ": "wypoczynkowy", "data_od": "2026-06-10", "data_do": "2026-06-12"})
    with pytest.raises(ValueError):
        service.correct_period(rec.id, "2026-06-04", "2026-06-11", "kolizja")


def test_idempotent_resave_not_blocked_as_overlap(service):
    p = service.prepare(ANNUAL)
    service.save(p.data, p.pdf)
    service.save(p.data, p.pdf)  # identyczna treść → idempotentnie, nie traktowane jako nakładanie
    assert len(service.list_records()) == 1


def test_default_settings(service):
    ent = {e.leave_type: e for e in service.settings(2026)}
    assert ent["wypoczynkowy"].active is True
    assert ent["wypoczynkowy"].limit_days == 26
    assert ent["ojcowski"].active is False  # hidden in the balance by default
    assert ent["opieka"].limit_hours == 16


def test_save_settings_and_read(service):
    service.save_settings(2026, {
        "wypoczynkowy": {"limit_dni": "20", "bilans_z_przeniesienia": "6"},
        "ojcowski": {"aktywny": True},
    })
    ent = {e.leave_type: e for e in service.settings(2026)}
    assert ent["wypoczynkowy"].limit_days == 20
    assert ent["wypoczynkowy"].carried_over == 6
    assert ent["ojcowski"].active is True
    assert ent["ojcowski"].limit_days == 14  # from the descriptor


def test_balance_uses_saved_settings(service):
    service.save_settings(2026, {"wypoczynkowy": {"limit_dni": "26", "bilans_z_przeniesienia": "0"}})
    p = service.prepare({"typ": "wypoczynkowy", "data_od": "2026-08-04", "data_do": "2026-08-08"})
    service.save(p.data, p.pdf)  # 4 working days, status pending
    items = {item.label: item for item in service.balance(2026)}
    current = items["Urlop wypoczynkowy (bieżący)"]
    assert current.planned == 4  # pending counts as planned
    assert current.used == 0
    assert current.remaining == 26


def test_holidays_returns_date_name_pairs(service):
    holidays = service.holidays(2026)
    assert ("2026-01-01", "Nowy Rok") in holidays
    # sorted ascending by date
    dates = [d for d, _ in holidays]
    assert dates == sorted(dates)


def test_create_applications_single_without_split(service):
    records = service.create_applications(ANNUAL, weekend_days=0)
    assert len(records) == 1
    assert records[0].leave_type == "wypoczynkowy"


def test_create_applications_splits_off_weekend_days(service):
    # August 2026 has one Saturday holiday (15 Aug) → capacity 1; carve off the trailing day.
    payload = {"typ": "wypoczynkowy", "imie_nazwisko": "Jan Kowalski",
               "data_od": "2026-08-10", "data_do": "2026-08-21"}
    records = service.create_applications(payload, weekend_days=1)
    assert len(records) == 2
    by_type = {r.leave_type: r for r in records}
    annual = by_type["wypoczynkowy"]
    comp = by_type["wolne_za_swieta"]
    assert annual.period.end_iso == "2026-08-20"  # trailing working day carved off
    assert annual.working_days == 9
    assert comp.period.start_iso == "2026-08-21" and comp.period.end_iso == "2026-08-21"
    assert comp.working_days == 1


def test_create_applications_clamps_to_month_capacity(service):
    # §16.1: request 9 days off, but August has capacity 1 → only one comp day is carved off.
    recs = service.create_applications(
        {"typ": "wypoczynkowy", "data_od": "2026-08-20", "data_do": "2026-08-21"}, weekend_days=9)
    assert {r.leave_type for r in recs} == {"wypoczynkowy", "wolne_za_swieta"}
    ojc = service.create_applications(
        {"typ": "ojcowski", "data_od": "2026-06-01", "data_do": "2026-06-14"}, weekend_days=3)
    assert [r.leave_type for r in ojc] == ["ojcowski"]


def test_split_rejected_when_month_has_no_saturday_holiday(service):
    # §16.1: July 2026 has no Saturday holiday → no split even if days are requested.
    recs = service.create_applications(
        {"typ": "wypoczynkowy", "data_od": "2026-07-06", "data_do": "2026-07-17"}, weekend_days=2)
    assert [r.leave_type for r in recs] == ["wypoczynkowy"]


def test_add_manual_weekend_off_rejected_without_capacity(service):
    # §16.1: a day off cannot be booked in a month without a Saturday holiday (July 2025).
    with pytest.raises(ValueError):
        service.add_manual({"typ": "wolne_za_swieta", "data_od": "2025-07-08", "data_do": "2025-07-08"})


def test_split_weekend_days_count_in_balance(service):
    # §16.1: the comp day settles in its own month. Leave in May 2025 (3 May is a Saturday
    # holiday) → the May line counts it.
    payload = {"typ": "wypoczynkowy", "data_od": "2025-05-05", "data_do": "2025-05-16"}
    service.create_applications(payload, weekend_days=1)
    may = next(i for i in service.balance(2025) if i.short_term and i.month == 5)
    assert may.planned == 1  # comp record is pending → planned


def test_single_shift_enabled_default_true(service):
    assert service.single_shift_enabled(2025) is True


def test_balance_saturday_holidays_lines_per_month(service):
    # §16.1: one highlighted line per month with a Saturday holiday (2025: May and November).
    items = [i for i in service.balance(2025) if i.short_term]
    months = {i.month for i in items}
    assert 5 in months and 11 in months
    may = next(i for i in items if i.month == 5)
    assert may.limit == 1 and may.remaining == 1  # one Saturday holiday in May, none used yet
    assert "maj 2025" in may.label


def test_single_shift_toggle_off_removes_lines(service):
    service.save_settings(2025, {"wolne_za_swieta": {"aktywny": False}})
    assert service.single_shift_enabled(2025) is False
    assert not any(i.short_term for i in service.balance(2025))


def test_change_status(service):
    p = service.prepare(ANNUAL)
    r = service.save(p.data, p.pdf)
    changed = service.change_status(r.id, "zaakceptowany")
    assert changed.status == Status.APPROVED


def test_change_status_no_record(service):
    from app.domain.errors import RecordNotFound

    with pytest.raises(RecordNotFound):
        service.change_status(999, "zaakceptowany")


def test_correct_period_recomputes_amount(service):
    p = service.prepare(ANNUAL)  # 04–08.08 = 4 working days
    r = service.save(p.data, p.pdf)
    corrected = service.correct_period(r.id, "2026-08-04", "2026-08-05", "L4")  # Tue–Wed = 2
    assert corrected.working_days == 2
    assert corrected.correction_reason == "L4"
    assert corrected.period.end_iso == "2026-08-05"
    assert corrected.original_period.end_iso == "2026-08-08"


def test_add_manual(service):
    r = service.add_manual({"typ": "wypoczynkowy", "data_od": "2026-05-04", "data_do": "2026-05-05"})
    assert r.source.value == "reczny"
    assert r.status == Status.APPROVED
    assert r.working_days == 2
    assert len(service.list_records()) == 1


def test_add_manual_weekend_off_day(service):
    # §16.2: the day off for a Saturday holiday can be added manually (e.g. in its month).
    r = service.add_manual({"typ": "wolne_za_swieta", "data_od": "2025-05-06", "data_do": "2025-05-06"})
    assert r.leave_type == "wolne_za_swieta"
    assert r.status == Status.APPROVED
    assert r.working_days == 1


def test_add_attachment_and_read(service):
    r = service.add_manual({"typ": "wypoczynkowy", "data_od": "2026-05-04", "data_do": "2026-05-05"})
    updated = service.add_attachment(r.id, b"%PDF-1.4", "application/pdf", "skan.pdf")
    assert updated.attachment_mime == "application/pdf"
    assert service.attachment(r.id) == (b"%PDF-1.4", "application/pdf", "skan.pdf")


def test_add_attachment_disallowed_mime(service):
    r = service.add_manual({"typ": "wypoczynkowy", "data_od": "2026-05-04", "data_do": "2026-05-05"})
    with pytest.raises(ValueError):
        service.add_attachment(r.id, b"anything", "text/plain", "z.txt")


def test_add_attachment_no_record(service):
    from app.domain.errors import RecordNotFound

    with pytest.raises(RecordNotFound):
        service.add_attachment(999, b"%PDF-1.4", "application/pdf", "x.pdf")


def test_delete_record(service):
    p = service.prepare(ANNUAL)
    r = service.save(p.data, p.pdf)
    assert service.delete_record(r.id) is True
    assert service.list_records() == []
    assert service.delete_record(r.id) is False


def test_list_records_filters_by_year(service):
    a = service.prepare(ANNUAL)
    service.save(a.data, a.pdf)
    b = service.prepare({**ANNUAL, "data_od": "2025-03-01", "data_do": "2025-03-03"})
    service.save(b.data, b.pdf)
    assert len(service.list_records(year=2026)) == 1
    assert len(service.list_records(year=2025)) == 1
    assert len(service.list_records()) == 2
