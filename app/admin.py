"""Narzędzia administracyjne (self-host) — §23.3: reset hasła bez poczty.

Uruchamiane komendą `python -m app reset-haslo <username> [<haslo>]` na serwerze.
Bez hasła w argumencie generuje losowe i je wypisuje.
"""
from __future__ import annotations

import secrets
from typing import Optional

from .infrastructure.persistence import SqliteUserRepository, default_data_dir, ensure_schema
from .infrastructure.security import BcryptPasswordHasher


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
