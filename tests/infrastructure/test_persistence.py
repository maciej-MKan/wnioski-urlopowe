"""Tests of the SQLite record repository on a temporary data directory."""
from __future__ import annotations

import pytest

from app.domain.leave_record import LeaveRecord
from app.domain.values import DateRange, Status
from app.infrastructure.persistence import SqliteLeaveRecordRepository

NOW = "2026-07-24T10:00:00"


@pytest.fixture
def repo(tmp_path) -> SqliteLeaveRecordRepository:
    return SqliteLeaveRecordRepository(user_id=1, data_dir=tmp_path)


def _record(pdf=b"%PDF-1.4 x", **overrides) -> LeaveRecord:
    data = {"typ": "wypoczynkowy", "imie_nazwisko": "Jan Kowalski",
            "data_od": "2026-08-04", "data_do": "2026-08-08"}
    data.update(overrides)
    return LeaveRecord.from_application(data, now=NOW, document=pdf)


def test_save_and_read_keeps_fields(repo):
    saved = repo.save(_record())
    read = repo.get(saved.id)
    assert read is not None
    assert read.leave_type == "wypoczynkowy"
    assert read.year == 2026
    assert read.status == Status.PENDING
    assert read.period == DateRange.from_strings("2026-08-04", "2026-08-08")
    assert read.data["imie_nazwisko"] == "Jan Kowalski"


def test_upsert_by_hash_does_not_duplicate(repo):
    r1 = repo.save(_record())
    r2 = repo.save(_record())
    assert r1.id == r2.id
    assert len(repo.list()) == 1


def test_different_data_gives_separate_records(repo):
    repo.save(_record())
    repo.save(_record(data_do="2026-08-09"))
    assert len(repo.list()) == 2


def test_document_saved_and_read(repo):
    saved = repo.save(_record(pdf=b"%PDF-1.7 tresc"))
    assert repo.document(saved.id) == b"%PDF-1.7 tresc"


def test_document_missing_for_nonexistent(repo):
    assert repo.document(999) is None


def test_list_filters_by_year(repo):
    repo.save(_record())
    repo.save(_record(data_od="2025-03-01", data_do="2025-03-03"))
    assert len(repo.list(year=2026)) == 1
    assert len(repo.list(year=2025)) == 1


def test_re_save_does_not_overwrite_status(repo):
    """The status is the record's property after creation — regenerating the PDF does not reset it."""
    approved = _record()
    approved.approve(NOW)
    saved = repo.save(approved)  # persisted as approved
    # Re-downloading the same PDF: a new aggregate with the same content, status pending.
    # The upsert (ON CONFLICT) updates only the PDF and marker — it does not undo the approval.
    repo.save(_record())
    assert repo.get(saved.id).status == Status.APPROVED


def test_update_changes_state(repo):
    saved = repo.save(_record())
    saved.working_days = 4
    saved.approve("2026-08-01T09:00:00")
    repo.update(saved)
    read = repo.get(saved.id)
    assert read.working_days == 4
    assert read.status == Status.APPROVED
    assert read.updated_at == "2026-08-01T09:00:00"


def test_update_without_id_raises(repo):
    with pytest.raises(ValueError):
        repo.update(_record())


def test_delete_removes_record_and_pdf(repo, tmp_path):
    saved = repo.save(_record(pdf=b"%PDF-1.7 x"))
    assert repo.delete(saved.id) is True
    assert repo.get(saved.id) is None
    assert repo.document(saved.id) is None
    # the PDF file is gone too
    assert list((tmp_path / "pdfs").glob("*.pdf")) == []


def test_attachment_save_read_and_replace(repo):
    r = repo.save(_record())
    repo.save_attachment(r.id, b"%PDF-1.4 a", "application/pdf", "a.pdf", NOW)
    assert repo.attachment(r.id) == (b"%PDF-1.4 a", "application/pdf", "a.pdf")
    # Replacement with a different type — the old file is not left as an orphan.
    repo.save_attachment(r.id, b"\xff\xd8\xff b", "image/jpeg", "b.jpg", NOW)
    content, mime, name = repo.attachment(r.id)
    assert (content, mime, name) == (b"\xff\xd8\xff b", "image/jpeg", "b.jpg")
    read = repo.get(r.id)
    assert read.attachment_mime == "image/jpeg"


def test_attachment_missing_for_nonexistent(repo):
    assert repo.attachment(999) is None
    assert repo.save_attachment(999, b"%PDF", "application/pdf", "x.pdf", NOW) is None


def test_attachment_disallowed_mime_raises(repo):
    r = repo.save(_record())
    with pytest.raises(ValueError):
        repo.save_attachment(r.id, b"tekst", "text/plain", "z.txt", NOW)


def test_delete_removes_attachment_too(repo, tmp_path):
    r = repo.save(LeaveRecord.manual(
        {"typ": "wypoczynkowy", "data_od": "2026-05-04", "data_do": "2026-05-05"}, now=NOW))
    repo.save_attachment(r.id, b"\xff\xd8\xff x", "image/jpeg", "x.jpg", NOW)
    repo.delete(r.id)
    assert list((tmp_path / "pdfs").glob("*")) == []


def test_delete_nonexistent_returns_false(repo):
    assert repo.delete(999) is False


def test_persistence_between_connections(repo, tmp_path):
    repo.save(_record())
    fresh = SqliteLeaveRecordRepository(user_id=1, data_dir=tmp_path)
    assert len(fresh.list()) == 1


def test_user_isolation(tmp_path):
    # §18: two users on the same database never see each other's records.
    a = SqliteLeaveRecordRepository(user_id=1, data_dir=tmp_path)
    b = SqliteLeaveRecordRepository(user_id=2, data_dir=tmp_path)
    ra = a.save(_record())
    assert len(a.list()) == 1
    assert b.list() == []              # user 2 sees nothing
    assert b.get(ra.id) is None        # cannot fetch across users
    assert b.delete(ra.id) is False    # cannot delete across users
    # Identical content for two users → two separate records (per-user namespaced hash).
    b.save(_record())
    assert len(a.list()) == 1 and len(b.list()) == 1


_V3_SCHEMA = """
CREATE TABLE entitlement (
    rok INTEGER NOT NULL, typ TEXT NOT NULL, aktywny INTEGER NOT NULL DEFAULT 1,
    limit_dni REAL, limit_godzin REAL, bilans_z_przeniesienia REAL, uwagi TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (rok, typ)
);
CREATE TABLE leave_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT, typ TEXT NOT NULL, rok INTEGER,
    za_okres TEXT NOT NULL DEFAULT 'biezacy', zrodlo TEXT NOT NULL DEFAULT 'wniosek',
    pdf_path TEXT, zalacznik_mime TEXT, zalacznik_nazwa TEXT, data_od TEXT, data_do TEXT,
    dni_robocze REAL, godziny REAL, dane_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'do_akceptacji',
    korekta_powod TEXT, data_od_pierwotna TEXT, data_do_pierwotna TEXT,
    tresc_hash TEXT UNIQUE, utworzono TEXT NOT NULL, zmieniono TEXT NOT NULL
);
"""


def test_v3_to_v4_migration_adopts_legacy_data(tmp_path):
    # §18: an old single-user database gets an owner account, and its data is assigned to it.
    import sqlite3

    from app.infrastructure.persistence import (
        SqliteEntitlementRepository,
        SqliteUserRepository,
        ensure_schema,
    )

    (tmp_path / "pdfs").mkdir()
    conn = sqlite3.connect(tmp_path / "wnioski.db")
    conn.executescript(_V3_SCHEMA)
    conn.execute(
        "INSERT INTO leave_record (typ, rok, dane_json, tresc_hash, utworzono, zmieniono) "
        "VALUES ('wypoczynkowy', 2026, '{\"typ\":\"wypoczynkowy\"}', 'hash-legacy', ?, ?)",
        (NOW, NOW),
    )
    conn.execute("INSERT INTO entitlement (rok, typ, aktywny) VALUES (2026, 'wypoczynkowy', 1)")
    conn.execute("PRAGMA user_version = 3")
    conn.commit()
    conn.close()

    ensure_schema(tmp_path)

    users = SqliteUserRepository(data_dir=tmp_path)
    assert users.count() == 1
    owner = users.get_by_username("owner")
    assert owner is not None and owner.id is not None

    adopted = SqliteLeaveRecordRepository(user_id=owner.id, data_dir=tmp_path)
    assert len(adopted.list()) == 1  # legacy record now belongs to the owner
    ents = SqliteEntitlementRepository(user_id=owner.id, data_dir=tmp_path)
    assert "wypoczynkowy" in ents.for_year(2026)
