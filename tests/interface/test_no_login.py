"""Tryb bez logowania (WNIOSKI_NO_LOGIN): jedyne konto auto-uwierzytelniane; brak konta
wymusza jego utworzenie; przy wielu kontach flaga nie działa (schodzimy do tokenu)."""
from __future__ import annotations

from typing import cast

import pytest
from fastapi.testclient import TestClient

from app.application.auth import AuthService
from app.application.services import LeaveService
from app.composition import create_app
from app.interface.api import Container
from tests.conftest import FakeHasher, FakeTokens, FakeUserRepository


def _client(users: FakeUserRepository, no_login: bool = True) -> TestClient:
    auth = AuthService(users=users, hasher=FakeHasher(), tokens=FakeTokens(), no_login=no_login)
    # Endpointy w tych testach (me/health/register) nie wołają service_for — atrapa wystarczy.
    container = Container(auth=auth, service_for=lambda _uid: cast(LeaveService, object()))
    return TestClient(create_app(container))


@pytest.fixture
def users() -> FakeUserRepository:
    return FakeUserRepository()


def test_sole_user_authenticated_without_token(users):
    users.create("solo", "h", "2026-01-01T00:00:00")
    client = _client(users)
    me = client.get("/api/me")  # brak nagłówka Authorization
    assert me.status_code == 200
    assert me.json()["username"] == "solo"


def test_health_signals_no_login_when_single_user(users):
    users.create("solo", "h", "2026-01-01T00:00:00")
    body = _client(users).get("/api/health").json()
    assert body["bez_logowania"] is True
    assert body["wymaga_konta"] is False
    assert body["rejestracja"] is False  # jedno konto już jest → rejestracja zablokowana


def test_no_user_requires_account_creation(users):
    client = _client(users)
    body = client.get("/api/health").json()
    assert body["bez_logowania"] is False
    assert body["wymaga_konta"] is True
    assert body["rejestracja"] is True  # wolno utworzyć pierwsze (jedyne) konto
    assert client.get("/api/me").status_code == 401  # brak konta → brak auto-usera

    r = client.post("/api/register", json={"username": "solo", "password": "tajne123"})
    assert r.status_code == 200
    # po utworzeniu konta auto-uwierzytelnianie działa bez tokenu
    assert client.get("/api/me").json()["username"] == "solo"


def test_second_registration_blocked_in_no_login(users):
    users.create("solo", "h", "2026-01-01T00:00:00")
    client = _client(users)
    r = client.post("/api/register", json={"username": "drugi", "password": "tajne123"})
    assert r.status_code == 403  # rejestracja wyłączona, gdy konto już istnieje


def test_multiple_users_fall_back_to_token(users):
    users.create("a", "h", "2026-01-01T00:00:00")
    users.create("b", "h", "2026-01-01T00:00:00")
    client = _client(users)
    body = client.get("/api/health").json()
    assert body["bez_logowania"] is False  # niejednoznaczne → tryb nieaktywny
    assert client.get("/api/me").status_code == 401  # wymaga tokenu


def test_flag_off_keeps_normal_auth(users):
    users.create("solo", "h", "2026-01-01T00:00:00")
    client = _client(users, no_login=False)
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/health").json()["bez_logowania"] is False
