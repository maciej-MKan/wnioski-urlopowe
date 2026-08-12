"""§23.3: administracyjny reset hasła (CLI)."""
from __future__ import annotations


def test_reset_password(tmp_path, monkeypatch):
    monkeypatch.setenv("WNIOSKI_DATA_DIR", str(tmp_path))
    from app.admin import reset_password
    from app.infrastructure.persistence import SqliteUserRepository, ensure_schema
    from app.infrastructure.security import BcryptPasswordHasher

    ensure_schema(tmp_path)
    users = SqliteUserRepository(tmp_path)
    users.create("ola", BcryptPasswordHasher().hash("stare"), "2026-01-01T00:00:00")

    ok, msg = reset_password("ola", "noweHaslo1")
    assert ok
    u = users.get_by_username("ola")
    assert u is not None and BcryptPasswordHasher().verify("noweHaslo1", u.password_hash)

    # nieznane konto → błąd
    ok2, _ = reset_password("nikt", "x")
    assert not ok2


def test_reset_password_generates_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("WNIOSKI_DATA_DIR", str(tmp_path))
    from app.admin import reset_password
    from app.infrastructure.persistence import SqliteUserRepository, ensure_schema
    from app.infrastructure.security import BcryptPasswordHasher

    ensure_schema(tmp_path)
    SqliteUserRepository(tmp_path).create("ola", BcryptPasswordHasher().hash("x"), "2026-01-01T00:00:00")
    ok, msg = reset_password("ola", None)
    assert ok and "Wygenerowane hasło:" in msg


def test_migrate_database(tmp_path, monkeypatch):
    """§23.1: migracja danych między bazami (tu SQLite→SQLite; logika ta sama co SQLite→Postgres)."""
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir(); dst.mkdir()
    monkeypatch.setenv("WNIOSKI_DATA_DIR", str(src))

    from sqlalchemy import create_engine, func, select

    from app.admin import migrate_database
    from app.domain.entitlement import Entitlement
    from app.domain.leave_record import LeaveRecord
    from app.domain.values import Status
    from app.infrastructure import persistence as P
    from app.infrastructure.persistence import (
        SqliteEntitlementRepository,
        SqliteLeaveRecordRepository,
        SqliteUserRepository,
        ensure_schema,
    )

    ensure_schema()
    u = SqliteUserRepository().create("ola", "h:x", "2026-01-01T00:00:00")
    SqliteLeaveRecordRepository(u.id).save(LeaveRecord.manual(
        {"typ": "wypoczynkowy", "data_od": "2026-06-01", "data_do": "2026-06-05"},
        now="2026-01-01T00:00:00", status=Status("zaakceptowany"), working_days=5.0, hours=None))
    SqliteEntitlementRepository(u.id).save(Entitlement(
        year=2026, leave_type="wypoczynkowy", active=True, limit_days=26,
        limit_hours=None, carried_over=None, notes=""))

    target_url = f"sqlite:///{dst / 'wnioski.db'}"
    ok, msg = migrate_database(target_url)
    assert ok, msg

    eng = create_engine(target_url)
    with eng.connect() as c:
        assert c.execute(select(func.count()).select_from(P.app_user)).scalar_one() == 1
        assert c.execute(select(func.count()).select_from(P.leave_record)).scalar_one() == 1
        assert c.execute(select(func.count()).select_from(P.entitlement)).scalar_one() == 1

    # ponowna migracja do niepustego celu → odmowa
    ok2, _ = migrate_database(target_url)
    assert not ok2


def _seed_sqlite(data_dir):
    from app.domain.entitlement import Entitlement
    from app.domain.leave_record import LeaveRecord
    from app.domain.values import Status
    from app.infrastructure.persistence import (
        SqliteEntitlementRepository,
        SqliteLeaveRecordRepository,
        SqliteUserRepository,
    )
    u = SqliteUserRepository(data_dir).create("ola", "h:x", "2026-01-01T00:00:00")
    SqliteLeaveRecordRepository(u.id, data_dir).save(LeaveRecord.manual(
        {"typ": "wypoczynkowy", "data_od": "2026-06-01", "data_do": "2026-06-05"},
        now="2026-01-01T00:00:00", status=Status("zaakceptowany"), working_days=5.0, hours=None))
    SqliteEntitlementRepository(u.id, data_dir).save(Entitlement(
        year=2026, leave_type="wypoczynkowy", active=True, limit_days=26,
        limit_hours=None, carried_over=None, notes=""))


def test_auto_migrate_fresh_does_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("WNIOSKI_DB_URL", raising=False)
    from app.admin import auto_migrate_on_startup
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir(); dst.mkdir()
    target = f"sqlite:///{dst / 'wnioski.db'}"
    assert auto_migrate_on_startup(target_url=target, data_dir=src) is None  # brak SQLite → świeży


def test_auto_migrate_upgrades_then_idempotent(tmp_path, monkeypatch):
    monkeypatch.delenv("WNIOSKI_DB_URL", raising=False)
    from sqlalchemy import create_engine, func, select

    from app.admin import auto_migrate_on_startup
    from app.infrastructure import persistence as P

    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir(); dst.mkdir()
    _seed_sqlite(src)
    target = f"sqlite:///{dst / 'wnioski.db'}"

    msg = auto_migrate_on_startup(target_url=target, data_dir=src)  # aktualizacja → migruje
    assert msg and "Zmigrowano" in msg
    with create_engine(target).connect() as c:
        assert c.execute(select(func.count()).select_from(P.app_user)).scalar_one() == 1

    # druga próba: cel ma dane → nic (idempotencja); SQLite źródłowe zostaje jako backup
    assert auto_migrate_on_startup(target_url=target, data_dir=src) is None
    assert (src / "wnioski.db").exists()
