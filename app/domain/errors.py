"""Domain exceptions — they signal business-rule violations, independent of HTTP."""
from __future__ import annotations


class DomainError(Exception):
    """Base exception of the domain layer."""


class UnknownLeaveType(DomainError):
    """The payload points to a leave type outside the registry."""

    def __init__(self, leave_type: object) -> None:
        super().__init__(f"Unknown application type: {leave_type!r}")
        self.leave_type = leave_type


class InvalidCorrection(DomainError):
    """Attempt to correct a period without giving a reason."""


class RecordNotFound(DomainError):
    """Reference to a record that does not exist."""

    def __init__(self, record_id: object) -> None:
        super().__init__(f"No record with id {record_id!r}")
        self.record_id = record_id


class AuthError(DomainError):
    """Base for authentication/authorization problems (§18)."""


class InvalidCredentials(AuthError):
    """Wrong username or password."""


class UsernameTaken(AuthError):
    """Registration with a username that already exists."""
