"""API auth tests (§18): protected endpoints, login/registration, current user.

Uses `raw_client` (auth ON, in-memory user store + fake hasher/tokens)."""
from __future__ import annotations


def test_protected_endpoint_requires_token(raw_client):
    assert raw_client.get("/api/rekordy").status_code == 401
    assert raw_client.get("/api/me").status_code == 401
    assert raw_client.get("/api/typy?rok=2026").status_code == 401


def test_public_endpoints_without_token(raw_client):
    assert raw_client.get("/api/health").json()["status"] == "ok"
    assert raw_client.get("/").status_code == 200  # kalendarz (strona)


def test_register_returns_token_and_identifies_user(raw_client):
    r = raw_client.post("/api/register", json={"username": "ola", "password": "tajne123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = raw_client.get("/api/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "ola"
    # a fresh account sees an empty (own) record list
    assert raw_client.get("/api/rekordy", headers=headers).json() == []


def test_token_login_flow(raw_client):
    raw_client.post("/api/register", json={"username": "ola", "password": "tajne123"})
    r = raw_client.post("/api/token", data={"username": "ola", "password": "tajne123"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"


def test_login_wrong_password_401(raw_client):
    raw_client.post("/api/register", json={"username": "ola", "password": "tajne123"})
    r = raw_client.post("/api/token", data={"username": "ola", "password": "nie-to"})
    assert r.status_code == 401


def test_register_duplicate_username_409(raw_client):
    raw_client.post("/api/register", json={"username": "ola", "password": "tajne123"})
    r = raw_client.post("/api/register", json={"username": "ola", "password": "inne456"})
    assert r.status_code == 409


def test_invalid_token_rejected(raw_client):
    assert raw_client.get("/api/me", headers={"Authorization": "Bearer sfalszowany"}).status_code == 401


def test_health_reports_registration_flag(raw_client):
    assert raw_client.get("/api/health").json()["rejestracja"] is True


def test_google_disabled_by_default(raw_client):
    assert raw_client.get("/api/health").json()["google"] is False
    assert raw_client.get("/api/auth/google/login").status_code == 404


def test_profile_requires_token(raw_client):
    assert raw_client.get("/api/profil").status_code == 401
    assert raw_client.put("/api/profil", json={}).status_code == 401


def test_profile_roundtrip_and_isolation(raw_client):
    # Rejestracja dwóch użytkowników.
    tok_a = raw_client.post("/api/register", json={"username": "ola", "password": "tajne123"}).json()["access_token"]
    tok_b = raw_client.post("/api/register", json={"username": "ala", "password": "tajne123"}).json()["access_token"]
    ha = {"Authorization": f"Bearer {tok_a}"}
    hb = {"Authorization": f"Bearer {tok_b}"}

    # Świeży profil jest pusty.
    assert raw_client.get("/api/profil", headers=ha).json() == {}

    # Zapis i odczyt profilu użytkownika A.
    dane = {"imie_nazwisko": "Jan Kowalski", "stanowisko": "Specjalista", "pracodawca": "ACME Sp. z o.o."}
    saved = raw_client.put("/api/profil", json=dane, headers=ha)
    assert saved.status_code == 200
    assert saved.json() == dane
    assert raw_client.get("/api/profil", headers=ha).json() == dane

    # Izolacja: profil B pozostaje pusty.
    assert raw_client.get("/api/profil", headers=hb).json() == {}


def test_google_flag_true_when_configured(container):
    from fastapi.testclient import TestClient

    from app.composition import create_app

    class DummyGoogle:
        async def login_redirect(self, request, redirect_uri): ...
        async def userinfo(self, request): return {}

    container.google = DummyGoogle()
    c = TestClient(create_app(container))
    assert c.get("/api/health").json()["google"] is True
