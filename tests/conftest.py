"""Shared test doubles and fixtures.

The ports architecture lets us swap the repository, generator and auth for in-memory doubles,
so domain, application and API tests run without SQLite, WeasyPrint or bcrypt/JWT. The API
`client` fixture bypasses auth via FastAPI dependency overrides (fixed user + fake service);
`raw_client` keeps auth on for the login/registration tests.
"""
from __future__ import annotations

from typing import Optional

import pytest

from app.application.auth import AuthService
from app.application.services import LeaveService
from app.domain.entitlement import Entitlement
from app.domain.leave_record import LeaveRecord
from app.domain.ports import (
    DocumentGenerator,
    EntitlementRepository,
    LeaveRecordRepository,
    UserRepository,
)
from app.domain.user import User


class FakeLeaveRecordRepository(LeaveRecordRepository):
    """In-memory repository with the same upsert-by-`content_hash` semantics as SQLite."""

    def __init__(self) -> None:
        self._by_hash: dict[str, LeaveRecord] = {}
        self._by_id: dict[int, LeaveRecord] = {}
        self._pdf: dict[int, bytes] = {}
        self._attachments: dict[int, tuple[bytes, str, Optional[str]]] = {}
        self._seq = 0

    def save(self, record: LeaveRecord) -> LeaveRecord:
        h = record.content_hash
        existing = self._by_hash.get(h)
        if existing is not None:
            record.id = existing.id
            existing.updated_at = record.updated_at
            if record.document is not None:
                self._pdf[existing.id] = record.document  # type: ignore[index]
            return existing
        self._seq += 1
        record.id = self._seq
        if record.document is not None:
            self._pdf[record.id] = record.document
        self._by_hash[h] = record
        self._by_id[record.id] = record
        return record

    def update(self, record: LeaveRecord) -> LeaveRecord:
        if record.id is None or record.id not in self._by_id:
            raise ValueError("Update requires an existing record.")
        self._by_id[record.id] = record
        for h, r in list(self._by_hash.items()):
            if r.id == record.id:
                self._by_hash[h] = record
        return record

    def list(self, year: Optional[int] = None) -> list[LeaveRecord]:
        records = list(self._by_id.values())
        if year is not None:
            records = [r for r in records if r.year == year]
        return sorted(records, key=lambda r: (r.period.start_iso or r.created_at, r.id or 0), reverse=True)

    def get(self, record_id: int) -> Optional[LeaveRecord]:
        return self._by_id.get(record_id)

    def document(self, record_id: int) -> Optional[bytes]:
        return self._pdf.get(record_id)

    def save_attachment(self, record_id, content, mime, name, now):
        record = self._by_id.get(record_id)
        if record is None:
            return None
        self._attachments[record_id] = (content, mime, name)
        record.attachment_mime = mime
        record.attachment_name = name
        record.updated_at = now
        return record

    def attachment(self, record_id):
        return self._attachments.get(record_id)

    def delete(self, record_id: int) -> bool:
        record = self._by_id.pop(record_id, None)
        if record is None:
            return False
        self._pdf.pop(record_id, None)
        self._attachments.pop(record_id, None)
        for h, r in list(self._by_hash.items()):
            if r.id == record_id:
                del self._by_hash[h]
        return True


class FakeEntitlementRepository(EntitlementRepository):
    """In-memory entitlement repository."""

    def __init__(self) -> None:
        self._data: dict[tuple[int, str], Entitlement] = {}

    def for_year(self, year: int) -> dict[str, Entitlement]:
        return {t: e for (y, t), e in self._data.items() if y == year}

    def save(self, entitlement: Entitlement) -> None:
        self._data[(entitlement.year, entitlement.leave_type)] = entitlement


class FakeDocumentGenerator:
    """Double of the `DocumentGenerator` port — without Jinja and WeasyPrint."""

    def html(self, data: dict) -> str:
        return f"<html data-typ='{data.get('typ')}'>podgląd</html>"

    def pdf(self, data: dict) -> bytes:
        return b"%PDF-1.4 fake " + data.get("typ", "").encode("utf-8")


class FakeUserRepository(UserRepository):
    """In-memory user store for auth tests."""

    def __init__(self) -> None:
        self._by_id: dict[int, User] = {}
        self._by_name: dict[str, User] = {}
        self._by_google: dict[str, User] = {}
        self._profiles: dict[int, dict] = {}
        self._seq = 0

    def get_by_username(self, username):
        return self._by_name.get(username)

    def get_by_google_sub(self, google_sub):
        return self._by_google.get(google_sub)

    def get(self, user_id):
        return self._by_id.get(user_id)

    def _add(self, username, password_hash, google_sub, now):
        self._seq += 1
        user = User(id=self._seq, username=username, password_hash=password_hash,
                    created_at=now, google_sub=google_sub)
        self._by_id[user.id] = user
        self._by_name[username] = user
        if google_sub:
            self._by_google[google_sub] = user
        return user

    def create(self, username, password_hash, now):
        return self._add(username, password_hash, None, now)

    def create_google(self, username, google_sub, now):
        return self._add(username, "", google_sub, now)

    def count(self):
        return len(self._by_id)

    def get_profile(self, user_id):
        return dict(self._profiles.get(user_id, {}))

    def save_profile(self, user_id, profile):
        clean = {str(k): ("" if v is None else str(v)) for k, v in (profile or {}).items()}
        self._profiles[user_id] = clean
        return clean


class FakeHasher:
    def hash(self, password: str) -> str:
        return "h:" + password

    def verify(self, password: str, hashed: str) -> bool:
        return hashed == "h:" + password


class FakeTokens:
    def issue(self, user_id: int) -> str:
        return f"tok-{user_id}"

    def user_id(self, token: str):
        rest = token[4:] if token.startswith("tok-") else ""
        return int(rest) if rest.isdigit() else None


@pytest.fixture
def repo() -> FakeLeaveRecordRepository:
    return FakeLeaveRecordRepository()


@pytest.fixture
def entitlements() -> FakeEntitlementRepository:
    return FakeEntitlementRepository()


@pytest.fixture
def generator() -> DocumentGenerator:
    return FakeDocumentGenerator()


@pytest.fixture
def clock():
    """Deterministic clock for reproducible timestamps."""
    return lambda: "2026-07-24T10:00:00"


@pytest.fixture
def service(repo, generator, entitlements, clock) -> LeaveService:
    return LeaveService(repository=repo, generator=generator, entitlements=entitlements, clock=clock)


@pytest.fixture
def users() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def auth_service(users) -> AuthService:
    return AuthService(users=users, hasher=FakeHasher(), tokens=FakeTokens())


@pytest.fixture
def container(service, auth_service):
    from app.interface.api import Container

    return Container(auth=auth_service, service_for=lambda user_id: service)


@pytest.fixture
def client(container, service):
    from fastapi.testclient import TestClient

    from app.composition import create_app
    from app.interface.api import current_user, get_service

    app = create_app(container)
    # Bypass auth for endpoint tests: fixed user + the fake service.
    app.dependency_overrides[current_user] = lambda: User(id=1, username="test")
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


@pytest.fixture
def raw_client(container):
    """Client with auth ON — for login/registration/401 tests."""
    from fastapi.testclient import TestClient

    from app.composition import create_app

    return TestClient(create_app(container))
