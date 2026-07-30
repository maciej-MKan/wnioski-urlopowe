"""User account — owner of leave records, entitlements and settings (§18 multi-tenancy).

The account is the tenant boundary: repositories are scoped by `user_id`, so a user only
ever sees their own data. `password_hash` is a persistence/auth detail carried here for the
login use case; interface views expose only `id` and `username`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class User:
    id: int | None
    username: str
    password_hash: str = ""  # bcrypt hash — empty for accounts that log in via Google (§18b)
    created_at: str = ""
    google_sub: str | None = None  # Google OpenID subject id, when linked
