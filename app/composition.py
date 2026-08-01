"""Composition root — the only place where the layers are wired together.

`create_app` builds the FastAPI application. In production it mounts the infrastructure
adapters (SQLite + WeasyPrint + bcrypt/JWT) — imported **lazily**, so tests providing their
own container do not pull in WeasyPrint. Inner layers know nothing about outer ones; they
meet here. §18: the container carries authentication and a per-user service factory.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .application.auth import AuthService
from .application.services import LeaveService
from .interface.api import Container, GoogleProvider, create_router

_STATIC = Path(__file__).resolve().parent / "static"


def _google_from_env() -> Optional[GoogleProvider]:
    """Builds the Google OIDC provider when `GOOGLE_CLIENT_ID`/`SECRET` are set (§18b)."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not (client_id and client_secret):
        return None
    from .infrastructure.oauth_google import GoogleOAuth

    return GoogleOAuth(client_id, client_secret)


def default_container() -> Container:
    """Production wiring: multi-user SQLite + WeasyPrint + bcrypt/JWT auth."""
    from .infrastructure.pdf import WeasyPrintDocumentGenerator
    from .infrastructure.persistence import (
        SqliteEntitlementRepository,
        SqliteLeaveRecordRepository,
        SqliteUserRepository,
        default_data_dir,
        ensure_schema,
    )
    from .infrastructure.security import BcryptPasswordHasher, TokenService, load_secret

    data_dir = default_data_dir()
    ensure_schema(data_dir)  # create/migrate schema; adopt legacy data to an owner account
    generator = WeasyPrintDocumentGenerator()  # shared, stateless
    tokens = TokenService(load_secret(data_dir))
    allow_register = os.environ.get("WNIOSKI_ALLOW_REGISTER", "1") != "0"
    no_login = os.environ.get("WNIOSKI_NO_LOGIN", "0") == "1"
    auth = AuthService(
        users=SqliteUserRepository(data_dir),
        hasher=BcryptPasswordHasher(),
        tokens=tokens,
        allow_register=allow_register,
        no_login=no_login,
    )

    def service_for(user_id: int) -> LeaveService:
        return LeaveService(
            repository=SqliteLeaveRecordRepository(user_id, data_dir),
            generator=generator,
            entitlements=SqliteEntitlementRepository(user_id, data_dir),
        )

    return Container(auth=auth, service_for=service_for, google=_google_from_env())


def create_app(container: Optional[Container] = None) -> FastAPI:
    """Creates the FastAPI application. Pass a `container` to inject doubles in tests."""
    if container is None:
        container = default_container()
    app = FastAPI(title="Generator wniosków urlopowych", docs_url="/api/docs")
    app.state.container = container
    # Session carries OAuth state/nonce/PKCE across the Google login→callback (§18b).
    app.add_middleware(SessionMiddleware, secret_key=os.environ.get("WNIOSKI_SECRET") or secrets.token_hex(16))
    app.include_router(create_router())
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
    return app
