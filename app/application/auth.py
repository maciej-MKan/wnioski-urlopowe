"""Authentication use cases (§18): register, login, resolve user from a bearer token.

Depends only on domain ports (`UserRepository`, `PasswordHasher`, `TokenIssuer`), so the
concrete algorithms (bcrypt, JWT) live in infrastructure and can be swapped (e.g. for OIDC).
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from ..domain.errors import InvalidCredentials, UsernameTaken
from ..domain.ports import PasswordHasher, TokenIssuer, UserRepository
from ..domain.user import User


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class AuthService:
    """Register accounts, exchange credentials for a token, resolve a token to a user."""

    def __init__(
        self,
        users: UserRepository,
        hasher: PasswordHasher,
        tokens: TokenIssuer,
        clock: Callable[[], str] = _now_iso,
        allow_register: bool = True,
        no_login: bool = False,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens
        self._clock = clock
        self._allow_register = allow_register
        self._no_login = no_login

    @property
    def no_login(self) -> bool:
        """Single-user mode without a login screen (§ tryb bez logowania)."""
        return self._no_login

    @property
    def allow_register(self) -> bool:
        # W trybie bez logowania rejestracja służy tylko utworzeniu jedynego konta (gdy baza pusta).
        if self._no_login:
            return self._users.count() == 0
        return self._allow_register

    def user_count(self) -> int:
        return self._users.count()

    def sole_user(self) -> Optional[User]:
        """Jedyne konto, gdy istnieje dokładnie jedno (tryb bez logowania), inaczej None."""
        return self._users.first() if self._users.count() == 1 else None

    def register(self, username: str, password: str) -> User:
        username = (username or "").strip()
        if not username or not password:
            raise InvalidCredentials("Podaj nazwę użytkownika i hasło.")
        if self._users.get_by_username(username) is not None:
            raise UsernameTaken(username)
        return self._users.create(username, self._hasher.hash(password), self._clock())

    def login(self, username: str, password: str) -> str:
        """Returns a bearer token for valid credentials, else raises `InvalidCredentials`."""
        user = self._users.get_by_username((username or "").strip())
        if user is None or user.id is None or not self._hasher.verify(password or "", user.password_hash):
            raise InvalidCredentials()
        return self._tokens.issue(user.id)

    def user_from_token(self, token: str) -> Optional[User]:
        user_id = self._tokens.user_id(token or "")
        return self._users.get(user_id) if user_id is not None else None

    def change_password(self, user_id: int, current: str, new: str) -> None:
        """Zmienia hasło po weryfikacji obecnego (§23.2). Rzuca `InvalidCredentials` przy błędzie."""
        user = self._users.get(user_id)
        if user is None:
            raise InvalidCredentials("Nie znaleziono konta.")
        if not (new or "").strip():
            raise InvalidCredentials("Podaj nowe hasło.")
        if not self._hasher.verify(current or "", user.password_hash):
            raise InvalidCredentials("Nieprawidłowe obecne hasło.")
        self._users.set_password(user_id, self._hasher.hash(new))

    def profile(self, user_id: int) -> dict:
        """User's saved default common fields (name, position, employer…) — §19."""
        return self._users.get_profile(user_id)

    def save_profile(self, user_id: int, profile: dict) -> dict:
        return self._users.save_profile(user_id, profile)

    def login_google(self, google_sub: str, email: Optional[str] = None) -> str:
        """Find-or-create a user by their Google subject id, then issue our bearer token (§18b)."""
        user = self._users.get_by_google_sub(google_sub)
        if user is None:
            username = self._unique_username(email or f"google_{google_sub[:8]}")
            user = self._users.create_google(username, google_sub, self._clock())
        assert user.id is not None
        return self._tokens.issue(user.id)

    def _unique_username(self, base: str) -> str:
        base = (base or "").strip() or "user"
        if self._users.get_by_username(base) is None:
            return base
        i = 2
        while self._users.get_by_username(f"{base}-{i}") is not None:
            i += 1
        return f"{base}-{i}"
