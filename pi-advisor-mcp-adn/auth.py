"""
Inbound authentication for the MCP HTTP endpoint.

Implemented as a plain ASGI middleware wrapped around the FastMCP
streamable-HTTP app, so it works regardless of FastMCP's own auth API
surface and versions.

Modes (AUTH_MODE):

  none      — no checks. Only acceptable for stdio/local testing.
              Refused at startup when the transport is http, unless
              explicitly overridden (see pi_mcp_server.py).

  api_key   — the request must carry an X-API-Key header matching one of
              AUTH_API_KEYS (constant-time comparison). Simple day-one
              option while the identity team provisions app registrations.

  entra_jwt — the request must carry "Authorization: Bearer <JWT>" issued
              by the configured Microsoft Entra ID tenant. The middleware
              validates: RS256 signature (against JWKS), issuer, audience,
              expiry. Then the caller is checked against the allowlist:

                AUTH_ALLOWED_USERS  — oid / upn / preferred_username / email
                AUTH_ALLOWED_GROUPS — any group object-ID in the 'groups' claim
                AUTH_ALLOWED_APPS   — appid / azp (daemon or connector apps)

              If ALL allowlists are empty, any valid tenant token passes
              (a warning is logged at startup).

JWKS sourcing for isolated networks:
  * AUTH_JWKS_FILE — a jwks.json exported ahead of time from
    https://login.microsoftonline.com/<tenant>/discovery/v2.0/keys
    (or the sovereign-cloud equivalent). Fully offline; re-export when
    Microsoft rotates signing keys (they overlap for weeks, so a monthly
    refresh is safe).
  * AUTH_JWKS_URL  — fetched and cached at first use and refreshed when an
    unknown key id (kid) appears; use when the identity endpoint is
    reachable from inside the private network.
"""

from __future__ import annotations

import hmac
import json
import logging
import threading
import time
from typing import Any, Dict, Optional

from config import config

logger = logging.getLogger("pi_advisor.auth")

_UNAUTHENTICATED_PATHS = {"/healthz"}  # liveness probe, no secrets returned


# --------------------------------------------------------------------------- #
# JWKS cache
# --------------------------------------------------------------------------- #

class _JWKSCache:
    """Thread-safe JWKS store, loadable from a local file or a URL."""

    def __init__(self) -> None:
        self._keys: Dict[str, Any] = {}       # kid -> JWK dict
        self._lock = threading.Lock()
        self._last_fetch = 0.0

    def _ingest(self, jwks: Dict[str, Any]) -> None:
        keys = {k["kid"]: k for k in jwks.get("keys", []) if "kid" in k}
        if not keys:
            raise ValueError("JWKS contained no usable keys")
        with self._lock:
            self._keys = keys
        logger.info("JWKS loaded: %d signing keys", len(keys))

    def load_file(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as fh:
            self._ingest(json.load(fh))

    def fetch_url(self, url: str) -> None:
        # Synchronous fetch is fine: called at startup and (rarely) on
        # key rotation. urllib avoids adding an event-loop dependency here.
        import ssl
        import urllib.request

        ctx = ssl.create_default_context(
            cafile=config.pi.ca_bundle or None
        )
        with urllib.request.urlopen(url, timeout=10, context=ctx) as resp:
            self._ingest(json.loads(resp.read().decode()))
        self._last_fetch = time.monotonic()

    def get(self, kid: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            jwk = self._keys.get(kid)
        if jwk is None and config.auth.jwks_url:
            # Unknown kid → possible key rotation; refetch at most once/minute.
            if time.monotonic() - self._last_fetch > 60:
                try:
                    self.fetch_url(config.auth.jwks_url)
                except Exception as exc:
                    logger.error("JWKS refresh failed: %s", exc)
            with self._lock:
                jwk = self._keys.get(kid)
        return jwk


_jwks = _JWKSCache()


def init_auth() -> None:
    """
    Validate auth configuration at startup and pre-load JWKS.
    Raises on unusable configuration so the server fails fast and loudly.
    """
    mode = config.auth.mode
    if mode == "none":
        logger.warning("AUTH_MODE=none — endpoint is UNAUTHENTICATED")
        return

    if mode == "api_key":
        if not config.auth.api_keys:
            raise ValueError("AUTH_MODE=api_key but AUTH_API_KEYS is empty")
        logger.info("Inbound auth: api_key (%d key(s) configured)", len(config.auth.api_keys))
        return

    if mode == "entra_jwt":
        if not config.auth.audience:
            raise ValueError("AUTH_MODE=entra_jwt requires AUTH_ENTRA_AUDIENCE")
        if not (config.auth.issuer or config.auth.tenant_id):
            raise ValueError("AUTH_MODE=entra_jwt requires AUTH_ENTRA_ISSUER or AUTH_ENTRA_TENANT_ID")
        if config.auth.jwks_file:
            _jwks.load_file(config.auth.jwks_file)
        elif config.auth.jwks_url:
            _jwks.fetch_url(config.auth.jwks_url)
        else:
            raise ValueError("AUTH_MODE=entra_jwt requires AUTH_JWKS_FILE or AUTH_JWKS_URL")
        if not (config.auth.allowed_users or config.auth.allowed_groups or config.auth.allowed_apps):
            logger.warning(
                "entra_jwt allowlists are EMPTY — any valid token from the "
                "tenant will be accepted. Set AUTH_ALLOWED_USERS/GROUPS/APPS."
            )
        logger.info("Inbound auth: entra_jwt (audience=%s)", config.auth.audience)
        return

    raise ValueError(f"Unknown AUTH_MODE: {mode!r} (expected none | api_key | entra_jwt)")


# --------------------------------------------------------------------------- #
# Validators
# --------------------------------------------------------------------------- #

def _expected_issuer() -> str:
    if config.auth.issuer:
        return config.auth.issuer
    return f"https://login.microsoftonline.com/{config.auth.tenant_id}/v2.0"


def _check_api_key(headers: Dict[bytes, bytes]) -> Optional[str]:
    """Return an error string, or None if authorised."""
    provided = headers.get(b"x-api-key", b"").decode()
    if not provided:
        return "Missing X-API-Key header"
    for key in config.auth.api_keys:
        if hmac.compare_digest(provided, key):
            return None
    return "Invalid API key"


def _check_entra_jwt(headers: Dict[bytes, bytes]) -> Optional[str]:
    """Return an error string, or None if authorised."""
    import jwt  # PyJWT
    from jwt import PyJWK

    authz = headers.get(b"authorization", b"").decode()
    if not authz.lower().startswith("bearer "):
        return "Missing bearer token"
    token = authz[7:].strip()

    try:
        unverified = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        return f"Malformed token: {exc}"

    kid = unverified.get("kid", "")
    jwk_dict = _jwks.get(kid)
    if jwk_dict is None:
        return f"Unknown signing key id: {kid}"

    try:
        key = PyJWK.from_dict(jwk_dict).key
        claims = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=config.auth.audience,
            issuer=_expected_issuer(),
            options={"require": ["exp", "aud", "iss"]},
        )
    except jwt.InvalidTokenError as exc:
        return f"Token validation failed: {exc}"

    # ---- allowlist -------------------------------------------------------
    allowed_users = {u.lower() for u in config.auth.allowed_users}
    allowed_groups = {g.lower() for g in config.auth.allowed_groups}
    allowed_apps = {a.lower() for a in config.auth.allowed_apps}

    if not (allowed_users or allowed_groups or allowed_apps):
        return None  # valid tenant token, no allowlist configured

    user_ids = {
        str(claims.get(c, "")).lower()
        for c in ("oid", "upn", "preferred_username", "email", "unique_name")
        if claims.get(c)
    }
    group_ids = {str(g).lower() for g in claims.get("groups", []) or []}
    app_ids = {
        str(claims.get(c, "")).lower()
        for c in ("appid", "azp")
        if claims.get(c)
    }

    if user_ids & allowed_users:
        return None
    if group_ids & allowed_groups:
        return None
    if app_ids & allowed_apps:
        return None

    subject = claims.get("preferred_username") or claims.get("appid") or claims.get("oid")
    logger.warning("Allowlist rejection for caller: %s", subject)
    return "Caller is not on the access list for this service"


# --------------------------------------------------------------------------- #
# ASGI middleware
# --------------------------------------------------------------------------- #

class AuthMiddleware:
    """Wraps the MCP ASGI app; rejects unauthenticated/unauthorised requests."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            # lifespan / websocket scopes pass through untouched
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _UNAUTHENTICATED_PATHS:
            await self._respond(send, 200, {"status": "alive"})
            return

        mode = config.auth.mode
        error: Optional[str] = None
        status = 401

        if mode == "api_key" or mode == "entra_jwt":
            headers = {k.lower(): v for k, v in scope.get("headers", [])}
            if mode == "api_key":
                error = _check_api_key(headers)
            else:
                error = _check_entra_jwt(headers)
                if error and "access list" in error:
                    status = 403

        if error:
            logger.info("Rejected %s %s: %s", scope.get("method"), path, error)
            await self._respond(send, status, {"error": error})
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _respond(send: Any, status: int, body: Dict[str, Any]) -> None:
        payload = json.dumps(body).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(payload)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": payload})
