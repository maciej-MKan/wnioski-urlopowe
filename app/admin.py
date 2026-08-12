"""Narzędzia administracyjne (self-host) — §23.3: reset hasła bez poczty.

Uruchamiane komendą `python -m app reset-haslo <username> [<haslo>]` na serwerze.
Bez hasła w argumencie generuje losowe i je wypisuje.
"""
from __future__ import annotations

import secrets
from typing import Optional

from .infrastructure.persistence import SqliteUserRepository, default_data_dir, ensure_schema
from .infrastructure.security import BcryptPasswordHasher


def migrate_database(target_url: str) -> tuple[bool, str]:
    """§23.1: kopiuje dane z bieżącej bazy **SQLite** do wskazanej bazy docelowej (Postgres).

    Przenosi wiersze `app_user`, `entitlement`, `leave_record` (z zachowaniem id). Pliki PDF/
    załączniki zostają na dysku (odwołania `pdf_path` niezmienione). Cel musi być pusty. Po
    migracji resetuje sekwencje SERIAL (Postgres). Zwraca (ok, komunikat).
    """
    from sqlalchemy import create_engine, func, insert, select, text

    from .infrastructure import persistence as P

    source = P._engine()  # źródło = bieżąca konfiguracja (bez WNIOSKI_DB_URL → SQLite)
    if source.dialect.name != "sqlite":
        return False, "Źródłem musi być SQLite (do migracji nie ustawiaj WNIOSKI_DB_URL na źródło)."
    ensure_schema()  # upewnij się, że źródłowy schemat jest kompletny
    target = create_engine(target_url, future=True)
    P._metadata.create_all(target)

    tables = [P.app_user, P.entitlement, P.leave_record]
    with target.connect() as t:
        existing = t.execute(select(func.count()).select_from(P.app_user)).scalar_one()
    if existing:
        return False, f"Baza docelowa nie jest pusta ({existing} kont) — przerwano dla bezpieczeństwa."

    counts: dict[str, int] = {}
    with source.connect() as s, target.begin() as t:
        for tbl in tables:
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
