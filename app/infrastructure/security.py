"""Password hashing (bcrypt) and JWT bearer tokens (§18).

Self-contained auth for a self-hosted deployment: no external identity provider. The signing
secret comes from `WNIOSKI_SECRET`, or is generated once and persisted to `<data_dir>/secret.key`
so issued tokens survive container restarts. Token-based (bearer) so the same scheme serves the
web SPA and a future native Android client; swappable for OIDC later behind the same seam.
"""
from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from typing import Optional

import bcrypt
import jwt

_ALG = "HS256"
_TOKEN_TTL_SECONDS = 30 * 24 * 3600  # 30 dni


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def load_secret(data_dir: Path) -> str:
    """Signing secret from env, or a stable random one persisted next to the database."""
    env = os.environ.get("WNIOSKI_SECRET")
    if env:
        return env
    path = Path(data_dir) / "secret.key"
    if path.exists():
        return path.read_text(encoding="ascii").strip()
    value = secrets.token_hex(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="ascii")
    return value


class BcryptPasswordHasher:
    """Adapter of the `PasswordHasher` port using bcrypt."""

    def hash(self, password: str) -> str:
        return hash_password(password)

    def verify(self, password: str, hashed: str) -> bool:
        return verify_password(password, hashed)


class TokenService:
    """Issues and verifies short JWTs whose `sub` is the user id (adapter of `TokenIssuer`)."""

    def __init__(self, secret: str, ttl_seconds: int = _TOKEN_TTL_SECONDS) -> None:
        self._secret = secret
        self._ttl = ttl_seconds

    def issue(self, user_id: int) -> str:
        now = int(time.time())
        payload = {"sub": str(user_id), "iat": now, "exp": now + self._ttl}
        return jwt.encode(payload, self._secret, algorithm=_ALG)

    def user_id(self, token: str) -> Optional[int]:
        """The user id encoded in a valid token, or None (expired/invalid/tampered)."""
        try:
            payload = jwt.decode(token, self._secret, algorithms=[_ALG])
            return int(payload["sub"])
        except (jwt.PyJWTError, KeyError, ValueError):
            return None
