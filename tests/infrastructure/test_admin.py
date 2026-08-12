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
