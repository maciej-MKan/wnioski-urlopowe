"""Tests of the entitlement repository (SQLite)."""
from __future__ import annotations

import pytest

from app.domain.entitlement import Entitlement
from app.infrastructure.persistence import SqliteEntitlementRepository


@pytest.fixture
def repo(tmp_path) -> SqliteEntitlementRepository:
    return SqliteEntitlementRepository(user_id=1, data_dir=tmp_path)


def test_save_and_read(repo):
    repo.save(Entitlement(year=2026, leave_type="wypoczynkowy", limit_days=26, carried_over=5))
    data = repo.for_year(2026)
    assert data["wypoczynkowy"].limit_days == 26
    assert data["wypoczynkowy"].carried_over == 5


def test_upsert_by_year_type(repo):
    repo.save(Entitlement(year=2026, leave_type="wypoczynkowy", limit_days=20))
    repo.save(Entitlement(year=2026, leave_type="wypoczynkowy", limit_days=26))
    data = repo.for_year(2026)
    assert len(data) == 1
    assert data["wypoczynkowy"].limit_days == 26


def test_year_isolation(repo):
    repo.save(Entitlement(year=2026, leave_type="wypoczynkowy", limit_days=26))
    repo.save(Entitlement(year=2025, leave_type="wypoczynkowy", limit_days=20))
    assert repo.for_year(2026)["wypoczynkowy"].limit_days == 26
    assert repo.for_year(2025)["wypoczynkowy"].limit_days == 20


def test_active_bool(repo):
    repo.save(Entitlement(year=2026, leave_type="opieka", active=False))
    assert repo.for_year(2026)["opieka"].active is False


def test_user_isolation(tmp_path):
    # §18: entitlements are scoped per user.
    a = SqliteEntitlementRepository(user_id=1, data_dir=tmp_path)
    b = SqliteEntitlementRepository(user_id=2, data_dir=tmp_path)
    a.save(Entitlement(year=2026, leave_type="wypoczynkowy", limit_days=26))
    assert a.for_year(2026)["wypoczynkowy"].limit_days == 26
    assert b.for_year(2026) == {}  # user 2 isolated
    b.save(Entitlement(year=2026, leave_type="wypoczynkowy", limit_days=10))
    assert a.for_year(2026)["wypoczynkowy"].limit_days == 26  # unchanged for user 1
    assert b.for_year(2026)["wypoczynkowy"].limit_days == 10
