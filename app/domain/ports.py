"""Ports — the interfaces through which the domain talks to the outside world.

The domain defines *what* it needs; infrastructure provides *how*. The repository is an
abstract base class (ABC) — an explicit inheritance contract; the document generator is a
`Protocol` — structural (duck) matching, convenient for test doubles. Both styles are
shown deliberately for teaching purposes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Protocol, runtime_checkable

from .entitlement import Entitlement
from .leave_record import LeaveRecord
from .user import User


class LeaveRecordRepository(ABC):
    """Persistent storage of leave records."""

    @abstractmethod
    def save(self, record: LeaveRecord) -> LeaveRecord:
        """Saves a record (upsert by `content_hash` — re-saving identical content refreshes
        the existing one). If `record.document` is set, also persists the PDF. Returns the
        saved record with an assigned `id`."""

    @abstractmethod
    def update(self, record: LeaveRecord) -> LeaveRecord:
        """Updates an existing record (by `id`) in its state fields: status, amount
        (`working_days`/`hours`), period and its correction, pool, change marker. Does not
        change identity (`leave_type`, `data`, `content_hash`, `created_at`)."""

    @abstractmethod
    def list(self, year: Optional[int] = None) -> list[LeaveRecord]:
        """Records (optionally from a given year), newest first."""

    @abstractmethod
    def get(self, record_id: int) -> Optional[LeaveRecord]:
        """Record by identifier or None."""

    @abstractmethod
    def document(self, record_id: int) -> Optional[bytes]:
        """The stored PDF bytes of the record or None."""

    @abstractmethod
    def save_attachment(
        self, record_id: int, content: bytes, mime: str, name: Optional[str], now: str
    ) -> Optional[LeaveRecord]:
        """Attaches a file (PDF/JPG) to the record, replacing the previous one. Returns the
        updated record or None when the record does not exist."""

    @abstractmethod
    def attachment(self, record_id: int) -> Optional[tuple[bytes, str, Optional[str]]]:
        """The record's attachment as (content, mime, original_name) or None."""

    @abstractmethod
    def delete(self, record_id: int) -> bool:
        """Deletes a record (and its file). Returns True when something was removed."""


class EntitlementRepository(ABC):
    """Persistent storage of entitlements (limits) per year and type."""

    @abstractmethod
    def for_year(self, year: int) -> dict[str, Entitlement]:
        """Entitlements saved for the given year, indexed by type."""

    @abstractmethod
    def save(self, entitlement: Entitlement) -> None:
        """Saves an entitlement (upsert by the year+type key)."""


class UserRepository(ABC):
    """Persistent storage of user accounts (§18)."""

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[User]:
        """User with the given username (incl. `password_hash`) or None."""

    @abstractmethod
    def get(self, user_id: int) -> Optional[User]:
        """User by id or None."""

    @abstractmethod
    def create(self, username: str, password_hash: str, now: str) -> User:
        """Creates a password user; caller ensures the username is free. Returns it with an id."""

    @abstractmethod
    def get_by_google_sub(self, google_sub: str) -> Optional[User]:
        """User linked to the given Google subject id, or None (§18b)."""

    @abstractmethod
    def create_google(self, username: str, google_sub: str, now: str) -> User:
        """Creates a user authenticated via Google (no password). Returns it with an id."""

    @abstractmethod
    def count(self) -> int:
        """Number of user accounts (used to decide owner seeding)."""

    @abstractmethod
    def first(self) -> Optional[User]:
        """The earliest-created user (lowest id), or None when there are none.

        Used by single-user, no-login mode to resolve the sole account.
        """

    @abstractmethod
    def set_password(self, user_id: int, password_hash: str) -> None:
        """Sets a new password hash for the account (§23.2 — zmiana hasła)."""

    @abstractmethod
    def delete(self, user_id: int) -> None:
        """Removes the account row (§23.4 — usunięcie konta). Dane tenantów kasuje warstwa wyżej."""

    @abstractmethod
    def get_profile(self, user_id: int) -> dict:
        """User's saved profile (default common fields) as a dict, or `{}` (§19)."""

    @abstractmethod
    def save_profile(self, user_id: int, profile: dict) -> dict:
        """Saves the user's profile; values are coerced to strings. Returns the stored dict."""


@runtime_checkable
class DocumentGenerator(Protocol):
    """Turns normalized application data into a document (HTML preview or PDF)."""

    def html(self, data: dict) -> str: ...

    def pdf(self, data: dict) -> bytes: ...


@runtime_checkable
class PasswordHasher(Protocol):
    """Hashes and verifies passwords (§18) — infrastructure provides the algorithm."""

    def hash(self, password: str) -> str: ...

    def verify(self, password: str, hashed: str) -> bool: ...


@runtime_checkable
class TokenIssuer(Protocol):
    """Issues and validates bearer tokens carrying the user id (§18)."""

    def issue(self, user_id: int) -> str: ...

    def user_id(self, token: str) -> Optional[int]: ...
