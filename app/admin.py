"""Narzędzia administracyjne (self-host) — §23.3: reset hasła bez poczty.

Uruchamiane komendą `python -m app reset-haslo <username> [<haslo>]` na serwerze.
Bez hasła w argumencie generuje losowe i je wypisuje.
"""
from __future__ import annotations

import secrets
from typing import Optional

from .infrastructure.persistence import SqliteUserRepository, default_data_dir, ensure_schema
from .infrastructure.security import BcryptPasswordHasher


def _sqlite_source_url(data_dir=None) -> str:
    """URL SQLite wskazujący na plik bazy w katalogu danych (niezależnie od `WNIOSKI_DB_URL`)."""
    from .infrastructure.persistence import default_data_dir as _ddir
    from pathlib import Path
    db = (Path(data_dir) if data_dir else _ddir()) / "wnioski.db"
    return f"sqlite:///{db}"


def _sqlite_path(url: str):
    from pathlib import Path
    return Path(url[len("sqlite:///"):]) if url.startswith("sqlite:///") else None


def migrate_database(target_url: str, source_url: Optional[str] = None) -> tuple[bool, str]:
    """§23.1: kopiuje dane ze źródłowej bazy **SQLite** (domyślnie plik w katalogu danych) do bazy
    docelowej (Postgres). Przenosi `app_user`, `entitlement`, `leave_record` (z zachowaniem id).
    Pliki PDF/załączniki zostają na dysku (`pdf_path` bez zmian). **Cel musi być pusty.** Po
    migracji resetuje sekwencje SERIAL (Postgres). Zwraca (ok, komunikat).
    """
    from sqlalchemy import create_engine, func, insert, select, text

    from .infrastructure import persistence as P

    source_url = source_url or _sqlite_source_url()
    source = create_engine(source_url, future=True)
    if source.dialect.name != "sqlite":
        return False, "Źródłem musi być SQLite."
    src_path = _sqlite_path(source_url)
    if src_path is not None:
        P._sqlite_legacy_upgrade(src_path)  # dociągnij stary schemat SQLite (v3→v4) przed kopią
    P._metadata.create_all(source)

    target = create_engine(target_url, future=True)
    P._metadata.create_all(target)
    with target.connect() as t:
        existing = t.execute(select(func.count()).select_from(P.app_user)).scalar_one()
    if existing:
        return False, f"Baza docelowa nie jest pusta ({existing} kont) — przerwano dla bezpieczeństwa."

    counts: dict[str, int] = {}
    with source.connect() as s, target.begin() as t:
        for tbl in (P.app_user, P.entitlement, P.leave_record):
            rows = [dict(r) for r in s.execute(select(tbl)).mappings().fetchall()]
            if rows:
                t.execute(insert(tbl), rows)
            counts[tbl.name] = len(rows)
        if target.dialect.name == "postgresql":
            for tbl in (P.app_user, P.leave_record):  # tabele z SERIAL id
                t.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{tbl.name}','id'), "
                    f"COALESCE((SELECT MAX(id) FROM {tbl.name}), 1), true)"
                ))
    return True, f"Zmigrowano wiersze: {counts}. Pliki PDF/załączniki pozostają na dysku."


def auto_migrate_on_startup(target_url: Optional[str] = None, data_dir=None) -> Optional[str]:
    """§23.1: idempotentna auto-migracja przy starcie backendu.

    - brak Postgresa (`WNIOSKI_DB_URL` ni: ustawiony/SQLite) → nic (zostajemy na SQLite);
    - cel (Postgres) **ma dane** → migracja już była lub świeży start z danymi → nic;
    - cel pusty + **istnieje SQLite z danymi** → aktualizacja: przenosimy dane (SQLite zostaje jako backup);
    - cel pusty + brak danych SQLite → świeży start → tylko schemat Postgresa (bez kopiowania).

    Zwraca komunikat, gdy coś zrobiono, inaczej `None`.
    """
    import logging
    import os

    from sqlalchemy import create_engine, func, select
    from sqlalchemy.exc import OperationalError

    from .infrastructure import persistence as P

    log = logging.getLogger("wnioski")
    target_url = target_url if target_url is not None else os.environ.get("WNIOSKI_DB_URL")
    source_url = _sqlite_source_url(data_dir)
    if not target_url or target_url == source_url:
        return None  # brak Postgresa / cel == źródło

    target = create_engine(target_url, future=True)
    P._metadata.create_all(target)
    with target.connect() as t:
        if t.execute(select(func.count()).select_from(P.app_user)).scalar_one() > 0:
            return None  # cel ma dane → nic (idempotencja)

    src_path = _sqlite_path(source_url)
    if src_path is None or not src_path.exists():
        return None  # świeży start (brak pliku SQLite) → tylko Postgres
    src = create_engine(source_url, future=True)
    try:
        with src.connect() as s:
            if s.execute(select(func.count()).select_from(P.app_user)).scalar_one() == 0:
                return None  # SQLite bez kont → nic do przeniesienia
    except OperationalError:
        return None  # SQLite bez tabel → nic

    ok, msg = migrate_database(target_url, source_url=source_url)
    log.warning("Auto-migracja bazy przy starcie: %s", msg)
    return msg if ok else None


def reset_password(username: str, new_password: Optional[str] = None) -> tuple[bool, str]:
    """Resetuje hasło konta administracyjnie (bez znajomości obecnego). Zwraca (ok, komunikat).

    Puste `new_password` → generuje bezpieczne losowe hasło i dołącza je do komunikatu.
    """
    data_dir = default_data_dir()
    ensure_schema(data_dir)
    users = SqliteUserRepository(data_dir)
    user = users.get_by_username(username)
    if user is None or user.id is None:
        return False, f"Nie znaleziono konta '{username}'."
    password = new_password or secrets.token_urlsafe(12)
    users.set_password(user.id, BcryptPasswordHasher().hash(password))
    suffix = "" if new_password else f" Wygenerowane hasło: {password}"
    return True, f"Hasło konta '{username}' zostało zresetowane.{suffix}"
