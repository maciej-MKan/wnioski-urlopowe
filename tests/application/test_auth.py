"""AuthService use cases (§18/§18b): local login/register and Google find-or-create."""
from __future__ import annotations

import pytest

from app.domain.errors import InvalidCredentials, UsernameTaken


def test_register_then_login(auth_service):
    auth_service.register("ola", "tajne123")
    token = auth_service.login("ola", "tajne123")
    assert auth_service.user_from_token(token).username == "ola"


def test_register_duplicate_raises(auth_service):
    auth_service.register("ola", "tajne123")
    with pytest.raises(UsernameTaken):
        auth_service.register("ola", "inne456")


def test_login_wrong_password_raises(auth_service):
    auth_service.register("ola", "tajne123")
    with pytest.raises(InvalidCredentials):
        auth_service.login("ola", "zle")


def test_login_google_creates_then_reuses(auth_service, users):
    t1 = auth_service.login_google("sub-123", "ola@example.com")
    t2 = auth_service.login_google("sub-123", "ola@example.com")
    assert t1 == t2                # same Google subject → same account
    assert users.count() == 1
    assert users.get_by_google_sub("sub-123").username == "ola@example.com"
    # a different subject → a separate account
    assert auth_service.login_google("sub-999", "inny@example.com") != t1
    assert users.count() == 2


def test_login_google_username_collision(auth_service, users):
    auth_service.register("ola@example.com", "tajne123")   # local account takes the name
    auth_service.login_google("sub-1", "ola@example.com")  # Google user gets a distinct username
    assert users.count() == 2
    assert users.get_by_google_sub("sub-1").username != "ola@example.com"


def test_google_only_account_cannot_password_login(auth_service):
    auth_service.login_google("sub-1", "ola@example.com")
    with pytest.raises(InvalidCredentials):
        auth_service.login("ola@example.com", "cokolwiek")
