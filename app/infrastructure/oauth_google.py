"""Google OpenID Connect provider (Authorization Code + PKCE) — optional (§18b).

Isolated so Authlib/httpx load only when Google login is configured. Uses the Starlette
session (SessionMiddleware) to carry state/nonce/PKCE between the login redirect and the
callback; Authlib verifies the ID token (signature via Google's JWKS, `iss`/`aud`/`exp`/nonce).
"""
from __future__ import annotations

_METADATA = "https://accounts.google.com/.well-known/openid-configuration"


class GoogleOAuth:
    """Adapter of the interface's `GoogleProvider` — wraps Authlib's Starlette client."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        from authlib.integrations.starlette_client import OAuth

        self._oauth = OAuth()
        self._oauth.register(
            name="google",
            server_metadata_url=_METADATA,
            client_id=client_id,
            client_secret=client_secret,
            client_kwargs={"scope": "openid email profile"},
        )

    async def login_redirect(self, request, redirect_uri):
        return await self._oauth.google.authorize_redirect(request, redirect_uri)

    async def userinfo(self, request) -> dict:
        token = await self._oauth.google.authorize_access_token(request)
        info = token.get("userinfo") or {}
        return {"sub": info.get("sub"), "email": info.get("email"), "name": info.get("name")}
