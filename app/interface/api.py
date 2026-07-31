"""HTTP router — a thin adapter translating requests into application-service calls.

Route paths, query keys (`rok`), payload keys and the multipart field name (`plik`) stay
Polish — they are the wire contract with the frontend. Handler names and internals are
English.

§18: data endpoints are protected. `get_service` resolves the current user from the bearer
token (via the `Container` on `app.state`) and yields a **user-scoped** `LeaveService`, so
every request only touches its own tenant's data. Page routes and `/api/health`/`/api/token`/
`/api/register` are public.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Protocol
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from ..application.auth import AuthService
from ..application.services import LeaveService
from ..domain.errors import (
    InvalidCorrection,
    InvalidCredentials,
    RecordNotFound,
    UnknownLeaveType,
    UsernameTaken,
)
from ..domain.user import User
from .serializers import (
    balance_item_to_json,
    entitlement_to_json,
    record_to_json,
    registry_to_json,
)

_log = logging.getLogger("wnioski")
_STATIC = Path(__file__).resolve().parent.parent / "static"

_ATTACHMENT_MAX = 5 * 1024 * 1024  # 5 MB — upper size limit of an attached file (§13.1)
# §19: deep link zwracający token do klienta Android (Google OAuth w Custom Tab/przeglądarce).
_NATIVE_REDIRECT = "pl.wnioski.urlopowe://auth"


class GoogleProvider(Protocol):
    """Optional Google OIDC provider (§18b) — interface-level, handles the HTTP redirect flow."""

    async def login_redirect(self, request: Request, redirect_uri: str) -> Any: ...

    async def userinfo(self, request: Request) -> dict: ...


@dataclass
class Container:
    """Wiring the router needs: authentication, a per-user service factory, optional Google (§18)."""

    auth: AuthService
    service_for: Callable[[int], LeaveService]
    google: Optional[GoogleProvider] = None


_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/token", auto_error=False)


def _container(request: Request) -> Container:
    return request.app.state.container


def current_user(request: Request, token: Optional[str] = Depends(_oauth2)) -> User:
    """Resolves the authenticated user from the bearer token, or 401."""
    user = _container(request).auth.user_from_token(token or "")
    if user is None:
        raise HTTPException(status_code=401, detail="Nieautoryzowany",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def get_service(request: Request, user: User = Depends(current_user)) -> LeaveService:
    """A `LeaveService` scoped to the current user's data."""
    return _container(request).service_for(user.id or 0)


def _detect_mime(content: bytes) -> str | None:
    """Recognizes the file type by signature (we trust neither the extension nor the client header)."""
    if content[:4] == b"%PDF":
        return "application/pdf"
    if content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    return None


def create_router() -> APIRouter:
    """Builds the router. The service and auth come per-request from `app.state.container`."""
    router = APIRouter()

    # --- Public pages ---------------------------------------------------------------
    # Kalendarz jest stroną główną; generator wniosków przeniesiony na /nowy.
    @router.get("/", response_class=HTMLResponse)
    @router.get("/kalendarz", response_class=HTMLResponse)  # alias wsteczny
    def calendar() -> FileResponse:
        return FileResponse(_STATIC / "kalendarz.html")

    @router.get("/nowy", response_class=HTMLResponse)
    def generator() -> FileResponse:
        return FileResponse(_STATIC / "index.html")

    @router.get("/ustawienia", response_class=HTMLResponse)
    def settings_page() -> FileResponse:
        return FileResponse(_STATIC / "ustawienia.html")

    # --- Auth (public) --------------------------------------------------------------
    @router.post("/api/token")
    def token(request: Request, form: OAuth2PasswordRequestForm = Depends()) -> dict:
        try:
            access = _container(request).auth.login(form.username, form.password)
        except InvalidCredentials as exc:
            raise HTTPException(status_code=401, detail="Zły login lub hasło") from exc
        return {"access_token": access, "token_type": "bearer"}

    @router.post("/api/register")
    def register(request: Request, payload: dict) -> dict:
        auth = _container(request).auth
        if not auth.allow_register:
            raise HTTPException(status_code=403, detail="Rejestracja wyłączona")
        username, password = payload.get("username", ""), payload.get("password", "")
        try:
            user = auth.register(username, password)
        except UsernameTaken as exc:
            raise HTTPException(status_code=409, detail="Nazwa użytkownika zajęta") from exc
        except InvalidCredentials as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        access = auth.login(username, password)  # auto-login after registration
        return {"id": user.id, "username": user.username, "access_token": access, "token_type": "bearer"}

    @router.get("/api/profil")
    def get_profil(request: Request, user: User = Depends(current_user)) -> dict:
        """User's saved default common fields (name, position, employer…) — §19."""
        return _container(request).auth.profile(user.id)

    @router.put("/api/profil")
    def save_profil(request: Request, payload: dict, user: User = Depends(current_user)) -> dict:
        return _container(request).auth.save_profile(user.id, payload)

    @router.get("/api/me")
    def me(user: User = Depends(current_user)) -> dict:
        return {"id": user.id, "username": user.username}

    @router.get("/api/auth/google/login")
    async def google_login(request: Request, native: bool = False):
        """Redirects to Google's consent screen (§18b). `native=1` → wróć do klienta Android (§19)."""
        google = _container(request).google
        if google is None:
            raise HTTPException(status_code=404, detail="Logowanie Google jest wyłączone")
        # Zapamiętaj w sesji cel powrotu — ta sama sesja przeglądarki obsłuży callback.
        request.session["google_native"] = bool(native)
        redirect_uri = str(request.url_for("google_callback"))
        return await google.login_redirect(request, redirect_uri)

    @router.get("/api/auth/google/callback", name="google_callback")
    async def google_callback(request: Request):
        """Google returns here; we verify, find-or-create the user and hand back our token."""
        container = _container(request)
        if container.google is None:
            raise HTTPException(status_code=404, detail="Logowanie Google jest wyłączone")
        native = bool(request.session.pop("google_native", False))
        base = _NATIVE_REDIRECT if native else ""  # klient natywny vs SPA (front web)
        try:
            info = await container.google.userinfo(request)
        except Exception:  # noqa: BLE001 — any OAuth failure → back to login with a flag
            _log.exception("Google OAuth callback failed")
            return RedirectResponse(f"{base}/#google_error=1" if not native else f"{base}#error=1")
        token = container.auth.login_google(info.get("sub"), info.get("email") or info.get("name"))
        # token w fragmencie (#) — nie trafia na serwer; klient (SPA lub Android) go odczytuje.
        return RedirectResponse(f"{base}#token={token}" if native else f"/#token={token}")

    # --- Protected data endpoints (user-scoped service) -----------------------------
    @router.get("/api/typy")
    def types(rok: int | None = None, service: LeaveService = Depends(get_service)) -> dict:
        """Registry of application types. With `?rok=RRRR` adds an `aktywny` flag per type."""
        active = {e.leave_type for e in service.settings(rok) if e.active} if rok is not None else None
        return registry_to_json(service.registry, active)

    @router.post("/api/generuj")
    def generate(payload: dict, service: LeaveService = Depends(get_service)) -> Response:
        try:
            prepared = service.prepare(payload)
        except UnknownLeaveType as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(prepared.file_name)}"}
        try:
            record = service.save(prepared.data, prepared.pdf)
            headers["X-Rekord-Id"] = str(record.id)
        except Exception:  # noqa: BLE001 — persistence is a side effect of generation
            _log.exception("Failed to save the leave record")

        return Response(content=prepared.pdf, media_type="application/pdf", headers=headers)

    @router.post("/api/wnioski")
    def create_applications(payload: dict, service: LeaveService = Depends(get_service)) -> dict:
        """Creates and saves the application(s) — 1 record, or 2 when `dni_za_swieto > 0` (§15)."""
        weekend = payload.pop("dni_za_swieto", 0)
        try:
            records = service.create_applications(payload, weekend_days=weekend)
        except UnknownLeaveType as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:  # np. reguły urlopu ojcowskiego (§20.2)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "wnioski": [
                {"id": r.id, "nazwa_pliku": service.application_file_name(r), "typ": r.leave_type}
                for r in records
            ]
        }

    @router.get("/api/dni-robocze")
    def working_days_count(data_od: str, data_do: str, service: LeaveService = Depends(get_service)) -> dict:
        """Working days in a range — bounds the §15 dialog's day count."""
        return {"dni_robocze": service.working_days_in(data_od, data_do)}

    @router.post("/api/podglad", response_class=HTMLResponse)
    def preview(payload: dict, service: LeaveService = Depends(get_service)) -> str:
        try:
            return service.preview(payload)
        except UnknownLeaveType as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/rekordy")
    def records(rok: int | None = None, service: LeaveService = Depends(get_service)) -> list[dict]:
        return [record_to_json(r) for r in service.list_records(rok)]

    @router.get("/api/swieta")
    def holidays(rok: int, service: LeaveService = Depends(get_service)) -> list[dict]:
        """Statutory days off in the given year (for the calendar overlay)."""
        return [{"data": d, "nazwa": name} for d, name in service.holidays(rok)]

    @router.get("/api/ustawienia")
    def settings(rok: int, service: LeaveService = Depends(get_service)) -> dict:
        """Entitlements (limits) for the given year — saved or default."""
        return {
            "rok": rok,
            "uprawnienia": [entitlement_to_json(e) for e in service.settings(rok)],
            "jednozmianowy": service.single_shift_enabled(rok),
        }

    @router.put("/api/ustawienia")
    def save_settings(rok: int, payload: dict, service: LeaveService = Depends(get_service)) -> dict:
        """Saves the year's entitlements."""
        service.save_settings(rok, payload)
        return {
            "rok": rok,
            "uprawnienia": [entitlement_to_json(e) for e in service.settings(rok)],
            "jednozmianowy": service.single_shift_enabled(rok),
        }

    @router.get("/api/bilans")
    def balance(rok: int, service: LeaveService = Depends(get_service)) -> list[dict]:
        """Leave usage balance (limit / used / planned / remaining)."""
        return [balance_item_to_json(item) for item in service.balance(rok)]

    @router.post("/api/rekordy/przelicz-wymiary")
    def recompute_amounts(service: LeaveService = Depends(get_service)) -> dict:
        """Backfills the amount (working days / hours) on existing records."""
        return {"zaktualizowano": service.recompute_amounts()}

    @router.get("/api/rekordy/{record_id}/pdf")
    def record_pdf(record_id: int, service: LeaveService = Depends(get_service)) -> Response:
        pdf = service.record_pdf(record_id)
        if pdf is None:
            raise HTTPException(status_code=404, detail="Brak PDF dla rekordu")
        return Response(content=pdf, media_type="application/pdf")

    @router.post("/api/rekordy/{record_id}/zalacznik")
    async def add_attachment(record_id: int, plik: UploadFile = File(...),
                             service: LeaveService = Depends(get_service)) -> dict:
        """Attaches a file (PDF/JPG) to a record. Type recognized by signature, 5 MB limit."""
        content = await plik.read()
        if len(content) > _ATTACHMENT_MAX:
            raise HTTPException(status_code=413, detail="Plik przekracza 5 MB.")
        mime = _detect_mime(content)
        if mime is None:
            raise HTTPException(status_code=415, detail="Dozwolone tylko PDF lub JPG.")
        try:
            record = service.add_attachment(record_id, content, mime, plik.filename)
        except RecordNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return record_to_json(record)

    @router.get("/api/rekordy/{record_id}/zalacznik")
    def record_attachment(record_id: int, service: LeaveService = Depends(get_service)) -> Response:
        """Serves the attached file with the correct MIME type (inline preview)."""
        result = service.attachment(record_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Brak załącznika dla rekordu")
        content, mime, name = result
        headers = {"Content-Disposition": f"inline; filename*=UTF-8''{quote(name or 'zalacznik')}"}
        return Response(content=content, media_type=mime, headers=headers)

    @router.post("/api/rekordy/reczny")
    def add_manual(payload: dict, service: LeaveService = Depends(get_service)) -> dict:
        """Adds leave taken outside the application (no PDF)."""
        status = payload.pop("status", "zaakceptowany")
        try:
            record = service.add_manual(payload, status=status)
        except UnknownLeaveType as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:  # invalid status / §16.1 capacity
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return record_to_json(record)

    @router.patch("/api/rekordy/{record_id}/status")
    def change_status(record_id: int, payload: dict, service: LeaveService = Depends(get_service)) -> dict:
        try:
            record = service.change_status(record_id, payload.get("status", ""))
        except RecordNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return record_to_json(record)

    @router.patch("/api/rekordy/{record_id}/okres")
    def correct_period(record_id: int, payload: dict, service: LeaveService = Depends(get_service)) -> dict:
        try:
            record = service.correct_period(
                record_id, payload.get("data_od", ""), payload.get("data_do", ""), payload.get("powod", "")
            )
        except RecordNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (InvalidCorrection, ValueError) as exc:  # ValueError: reguły ojcowskiego (§20.2)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return record_to_json(record)

    @router.delete("/api/rekordy/{record_id}", status_code=204)
    def delete_record(record_id: int, service: LeaveService = Depends(get_service)) -> Response:
        if not service.delete_record(record_id):
            raise HTTPException(status_code=404, detail="Brak rekordu")
        return Response(status_code=204)

    @router.get("/api/health")
    def health(request: Request) -> dict:
        # `srodowisko` (prod/dev) → badge w UI; `rejestracja` → czy pokazać formularz rejestracji.
        container = _container(request)
        return {
            "status": "ok",
            "srodowisko": os.environ.get("WNIOSKI_ENV", "prod"),
            "rejestracja": container.auth.allow_register,
            "google": container.google is not None,
        }

    return router
