"""
Async PI Web API client — ADN edition.

Handles authentication, session management, connection pooling, retries,
and provides convenience wrappers with selectedFields support to minimise
response payloads.

Supported PI_AUTH_METHOD values:

  kerberos — Windows Integrated Security via SSPI (pyspnego). A SPNEGO
             Negotiate token is attached to every request. By default the
             token is acquired for the identity of the running process
             (the Windows service account), which is the standard setup
             for the Kerberos PI Web API gateway. Explicit domain
             credentials can be supplied via PI_KERBEROS_USERNAME/PASSWORD.

  oauth    — Client-credentials flow against the OAuth PI Web API gateway.
             The access token is fetched from PI_OAUTH_TOKEN_URL, cached,
             and refreshed automatically 60 s before expiry.

  bearer   — A static token supplied out-of-band via PI_BEARER_TOKEN.

  basic    — Username/password (POC / lab use only).

TLS: PI_CA_BUNDLE points at the internal enterprise CA chain (PEM). Use it
instead of PI_VERIFY_SSL=false whenever the gateway certificate is issued
by an internal CA.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import ssl
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp

from config import config

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


def _build_basic_header(username: str, password: str) -> str:
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {creds}"


# --------------------------------------------------------------------------- #
# Auth providers
# --------------------------------------------------------------------------- #

class _KerberosAuth:
    """
    SPNEGO/Negotiate token provider backed by pyspnego.

    On Windows, pyspnego uses SSPI, so no keytab or MIT Kerberos install is
    required — the token is minted from the logon session of the service
    account the process runs as (or from explicit credentials if given).

    A fresh security context is created per request. This costs ~1 ms via
    SSPI and avoids all multi-request context bookkeeping; for a <20-user
    deployment the overhead is irrelevant.
    """

    def __init__(self) -> None:
        cfg = config.pi
        self._hostname = cfg.kerberos_hostname or (urlparse(cfg.url).hostname or "")
        self._service = cfg.kerberos_service or "HTTP"
        self._username = cfg.kerberos_username
        self._password = cfg.kerberos_password

    def token_header(self) -> str:
        import spnego  # imported lazily so non-kerberos setups don't need it

        ctx = spnego.client(
            username=self._username,
            password=self._password,
            hostname=self._hostname,
            service=self._service,
            protocol="negotiate",
        )
        token = ctx.step(None)
        if not token:
            raise ConnectionError(
                f"SSPI produced an empty Negotiate token for "
                f"{self._service}/{self._hostname} — check the SPN and that the "
                f"process runs as a domain account"
            )
        return "Negotiate " + base64.b64encode(token).decode()


class _OAuthClientCredentials:
    """
    Token cache + refresh for the OAuth PI Web API gateway
    (client-credentials grant).
    """

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def token_header(self, session: aiohttp.ClientSession) -> str:
        # Fast path without the lock
        if self._token and time.monotonic() < self._expires_at - 60:
            return f"Bearer {self._token}"

        async with self._lock:
            if self._token and time.monotonic() < self._expires_at - 60:
                return f"Bearer {self._token}"

            cfg = config.pi
            if not (cfg.oauth_token_url and cfg.oauth_client_id and cfg.oauth_client_secret):
                raise ValueError(
                    "PI_AUTH_METHOD=oauth requires PI_OAUTH_TOKEN_URL, "
                    "PI_OAUTH_CLIENT_ID and PI_OAUTH_CLIENT_SECRET"
                )

            form: Dict[str, str] = {
                "grant_type": "client_credentials",
                "client_id": cfg.oauth_client_id,
                "client_secret": cfg.oauth_client_secret,
            }
            if cfg.oauth_scope:
                form["scope"] = cfg.oauth_scope
            if cfg.oauth_resource:
                form["resource"] = cfg.oauth_resource

            async with session.post(
                cfg.oauth_token_url,
                data=form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                body = await resp.json(content_type=None)
                if resp.status != 200 or "access_token" not in body:
                    raise PermissionError(
                        f"OAuth token request failed ({resp.status}): "
                        f"{str(body)[:300]}"
                    )
                self._token = body["access_token"]
                self._expires_at = time.monotonic() + int(body.get("expires_in", 3600))
                logger.info("OAuth token acquired (expires in %ss)", body.get("expires_in", 3600))
            return f"Bearer {self._token}"


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #

class PIWebAPIClient:
    """
    Async client for AVEVA PI Web API.

    Create one instance per process; call ``close()`` on shutdown.
    Thread-safe: session is recreated per-event-loop if needed.
    """

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = asyncio.Lock()
        self._kerberos: Optional[_KerberosAuth] = None
        self._oauth: Optional[_OAuthClientCredentials] = None
        method = config.pi.auth_method
        if method in ("kerberos", "negotiate"):
            self._kerberos = _KerberosAuth()
        elif method == "oauth":
            self._oauth = _OAuthClientCredentials()

    # ------------------------------------------------------------------ #
    # Session lifecycle
    # ------------------------------------------------------------------ #

    def _build_ssl_ctx(self) -> ssl.SSLContext | bool:
        if not config.pi.verify_ssl:
            return False
        if config.pi.ca_bundle:
            return ssl.create_default_context(cafile=config.pi.ca_bundle)
        return ssl.create_default_context()

    def _make_connector(self) -> aiohttp.TCPConnector:
        return aiohttp.TCPConnector(
            limit=config.pi.connection_limit,
            limit_per_host=config.pi.per_host_limit,
            ttl_dns_cache=300,
            use_dns_cache=True,
            ssl=self._build_ssl_ctx(),
        )

    def _build_default_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        cfg = config.pi
        # Static header auth methods go on the session; per-request methods
        # (kerberos, oauth) are added in _auth_headers().
        if cfg.auth_method == "basic" and cfg.username and cfg.password:
            headers["Authorization"] = _build_basic_header(cfg.username, cfg.password)
        elif cfg.auth_method == "bearer" and cfg.bearer_token:
            headers["Authorization"] = f"Bearer {cfg.bearer_token}"
        return headers

    async def _ensure_session(self) -> aiohttp.ClientSession:
        loop = asyncio.get_event_loop()
        async with self._lock:
            if self._session is None or self._session_loop is not loop:
                if self._session and not self._session.closed:
                    await self._session.close()
                timeout = aiohttp.ClientTimeout(
                    total=config.pi.timeout,
                    connect=10,
                    sock_read=config.pi.timeout,
                )
                self._session = aiohttp.ClientSession(
                    connector=self._make_connector(),
                    headers=self._build_default_headers(),
                    timeout=timeout,
                )
                self._session_loop = loop
        return self._session

    async def _auth_headers(self, session: aiohttp.ClientSession) -> Dict[str, str]:
        """Per-request Authorization header for kerberos / oauth methods."""
        if self._kerberos is not None:
            # SSPI call is synchronous but ~1 ms; run inline.
            return {"Authorization": self._kerberos.token_header()}
        if self._oauth is not None:
            return {"Authorization": await self._oauth.token_header(session)}
        return {}

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ------------------------------------------------------------------ #
    # Core request
    # ------------------------------------------------------------------ #

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict] = None,
        retries: int = 3,
    ) -> Any:
        url = config.pi.url.rstrip("/") + "/" + path.lstrip("/")
        session = await self._ensure_session()
        last_exc: Exception = RuntimeError("No attempts made")

        for attempt in range(retries):
            try:
                headers = await self._auth_headers(session)
                async with session.request(
                    method, url, params=params, json=json, headers=headers or None
                ) as resp:
                    if resp.status in _RETRYABLE_STATUSES:
                        wait = 2 ** attempt
                        logger.warning("PI API %s %s → %d, retry in %ds", method, path, resp.status, wait)
                        await asyncio.sleep(wait)
                        continue
                    if resp.status == 401:
                        # With kerberos, a single 401 can be a stale/failed
                        # negotiation — retry once with a fresh token.
                        if self._kerberos is not None and attempt < retries - 1:
                            logger.warning("PI API 401 with kerberos — retrying with fresh token")
                            continue
                        raise PermissionError(f"PI Web API 401 — check credentials/identity ({path})")
                    if resp.status == 403:
                        raise PermissionError(f"PI Web API 403 — access denied ({path})")
                    if resp.status == 404:
                        raise FileNotFoundError(f"PI Web API 404 — not found ({path})")
                    resp.raise_for_status()
                    if resp.content_type == "application/json":
                        return await resp.json()
                    return await resp.text()
            except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as exc:
                last_exc = exc
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    logger.warning("PI API connection error (attempt %d/%d): %s", attempt + 1, retries, exc)

        raise ConnectionError(f"PI Web API request failed after {retries} attempts: {last_exc}")

    async def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: Optional[Dict] = None) -> Any:
        return await self._request("POST", path, json=json)

    # ------------------------------------------------------------------ #
    # High-level helpers
    # ------------------------------------------------------------------ #

    async def test_connection(self) -> Dict[str, Any]:
        t0 = time.monotonic()
        data = await self.get("/")
        return {
            "ok": True,
            "response_ms": round((time.monotonic() - t0) * 1000),
            "version": data.get("Version", "unknown"),
            "auth_method": config.pi.auth_method,
            "links": list((data.get("Links") or {}).keys()),
        }

    # ---- Asset Framework -------------------------------------------------

    async def get_af_servers(self) -> List[Dict]:
        data = await self.get("/assetservers")
        return data.get("Items", [])

    async def get_af_databases(self, server_webid: str) -> List[Dict]:
        data = await self.get(f"/assetservers/{server_webid}/assetdatabases")
        return data.get("Items", [])

    async def fetch_all_af_elements(
        self,
        database_webid: str,
        max_count: int = 10000,
        selected_fields: str = "Items.WebId;Items.Name;Items.Description;Items.Path;Items.TemplateName;Items.HasChildren",
    ) -> List[Dict]:
        """
        Fetch every element in a database recursively (used by the indexing pipeline).
        GET /assetdatabases/{webid}/elements?searchFullHierarchy=true
        """
        data = await self.get(
            f"/assetdatabases/{database_webid}/elements",
            params={
                "searchFullHierarchy": "true",
                "maxCount": max_count,
                "selectedFields": selected_fields,
            },
        )
        return data.get("Items", [])

    async def search_af_elements_by_query(
        self,
        database_webid: str,
        query: str,
        *,
        template_name: str = "",
        max_count: int = 500,
        selected_fields: str = "Items.Name;Items.WebId;Items.Path;Items.TemplateName;Items.HasChildren",
    ) -> List[Dict]:
        """
        Query-based element search.
        GET /elements/search?databaseWebId=...&query=...
        Pass the query verbatim (e.g. 'Name:Tank*') — no extra wrapping.
        """
        params: Dict[str, Any] = {
            "databaseWebId": database_webid,
            "query": query,
            "maxCount": max_count,
            "selectedFields": selected_fields,
        }
        if template_name:
            params["templateName"] = template_name
        data = await self.get("/elements/search", params=params)
        return data.get("Items", [])

    async def get_element_children(
        self,
        element_webid: str,
        selected_fields: str = "Items.WebId;Items.Name;Items.Description;Items.Path;Items.TemplateName;Items.HasChildren",
    ) -> List[Dict]:
        data = await self.get(
            f"/elements/{element_webid}/elements",
            params={"selectedFields": selected_fields},
        )
        return data.get("Items", [])

    async def get_element_by_path(
        self,
        path: str,
        selected_fields: str = "WebId;Name;Description;Path;TemplateName;HasChildren",
    ) -> Optional[Dict]:
        """
        Resolve a single AF element by its full path.
        Returns the element dict, or None if not found.
        Path format: \\\\AFServer\\Database\\Element\\SubElement
        GET /elements?path={path}
        """
        try:
            return await self.get(
                "/elements",
                params={"path": path, "selectedFields": selected_fields},
            )
        except FileNotFoundError:
            return None

    async def search_descendants(
        self,
        element_webid: str,
        max_count: int = 10000,
        selected_fields: str = "Items.WebId;Items.Name;Items.Description;Items.Path;Items.TemplateName;Items.HasChildren",
    ) -> List[Dict]:
        """
        All descendant elements within a subtree (for root-scoped indexing).
        GET /elements/{webid}/elements?searchFullHierarchy=true
        Does NOT include the root element itself.
        """
        data = await self.get(
            f"/elements/{element_webid}/elements",
            params={
                "searchFullHierarchy": "true",
                "maxCount": max_count,
                "selectedFields": selected_fields,
            },
        )
        return data.get("Items", [])

    async def get_element_attributes(
        self,
        element_webid: str,
        max_count: int = 100,
        selected_fields: str = "Items.WebId;Items.Name;Items.Description;Items.Type;Items.DefaultUnitsName;Items.DataReferencePlugIn",
    ) -> List[Dict]:
        data = await self.get(
            f"/elements/{element_webid}/attributes",
            params={"maxCount": max_count, "selectedFields": selected_fields},
        )
        return data.get("Items", [])

    # ---- Batch attribute fetching with concurrency limit -------------------

    async def batch_get_attributes(
        self,
        element_webids: List[str],
        concurrency: int = 20,
    ) -> Dict[str, List[Dict]]:
        """
        Fetch attributes for many elements concurrently.
        Returns {element_webid: [attribute_dicts]}.
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def _fetch(webid: str) -> tuple[str, List[Dict]]:
            async with semaphore:
                try:
                    attrs = await self.get_element_attributes(webid)
                    return webid, attrs
                except Exception as exc:
                    logger.warning("Failed to fetch attributes for %s: %s", webid, exc)
                    return webid, []

        results = await asyncio.gather(*[_fetch(w) for w in element_webids])
        return dict(results)

    # ---- Time-series data ------------------------------------------------

    async def get_stream_value(
        self,
        attribute_webid: str,
        selected_fields: str = "Timestamp;Value;UnitsAbbreviation;Good",
    ) -> Dict:
        return await self.get(
            f"/streams/{attribute_webid}/value",
            params={"selectedFields": selected_fields},
        )

    async def get_stream_recorded(
        self,
        attribute_webid: str,
        *,
        start_time: str = "*-1d",
        end_time: str = "*",
        max_count: int = 10000,
        selected_fields: str = "Items.Timestamp;Items.Value;Items.UnitsAbbreviation;Items.Good",
    ) -> List[Dict]:
        params = {
            "startTime": start_time,
            "endTime": end_time,
            "maxCount": max_count,
            "selectedFields": selected_fields,
        }
        data = await self.get(f"/streams/{attribute_webid}/recorded", params=params)
        return data.get("Items", [])

    async def get_stream_interpolated(
        self,
        attribute_webid: str,
        *,
        start_time: str = "*-1d",
        end_time: str = "*",
        interval: str = "1h",
        selected_fields: str = "Items.Timestamp;Items.Value;Items.UnitsAbbreviation",
    ) -> List[Dict]:
        params = {
            "startTime": start_time,
            "endTime": end_time,
            "interval": interval,
            "selectedFields": selected_fields,
        }
        data = await self.get(f"/streams/{attribute_webid}/interpolated", params=params)
        return data.get("Items", [])

    async def get_stream_summary(
        self,
        attribute_webid: str,
        *,
        start_time: str = "*-1d",
        end_time: str = "*",
        summary_types: str = "Average,Minimum,Maximum,StdDev",
        selected_fields: str = "Items.Type;Items.Value.Value;Items.Value.Timestamp",
    ) -> List[Dict]:
        params = {
            "startTime": start_time,
            "endTime": end_time,
            "summaryType": summary_types,
            "selectedFields": selected_fields,
        }
        data = await self.get(f"/streams/{attribute_webid}/summary", params=params)
        return data.get("Items", [])

    async def get_streamset_current(
        self,
        element_webid: str,
        name_filter: str = "*",
        selected_fields: str = "Items.Name;Items.Value;Items.Timestamp;Items.UnitsAbbreviation",
    ) -> List[Dict]:
        """All current attribute values for an element in one call."""
        params = {
            "nameFilter": name_filter,
            "selectedFields": selected_fields,
        }
        data = await self.get(f"/streamsets/{element_webid}/value", params=params)
        return data.get("Items", [])

    async def batch_get_stream_values(
        self,
        attribute_webids: List[str],
        concurrency: int = 20,
    ) -> Dict[str, Any]:
        """
        Fetch current values for multiple attribute WebIds concurrently.
        Returns {webid: value_dict}.
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def _fetch(webid: str) -> tuple[str, Any]:
            async with semaphore:
                try:
                    val = await self.get_stream_value(webid)
                    return webid, val
                except Exception as exc:
                    logger.warning("Failed to fetch value for %s: %s", webid, exc)
                    return webid, None

        results = await asyncio.gather(*[_fetch(w) for w in attribute_webids])
        return dict(results)

    # ---- Data servers ----------------------------------------------------

    async def get_data_servers(self) -> List[Dict]:
        data = await self.get("/dataservers")
        return data.get("Items", [])

    async def search_points(
        self,
        server_webid: str,
        query: str,
        max_count: int = 500,
        selected_fields: str = "Items.Name;Items.WebId;Items.Descriptor;Items.PointClass;Items.PointType",
    ) -> List[Dict]:
        params = {
            "query": query,
            "maxCount": max_count,
            "selectedFields": selected_fields,
        }
        data = await self.get(f"/dataservers/{server_webid}/points", params=params)
        return data.get("Items", [])


# Module-level singleton
_client: Optional[PIWebAPIClient] = None


def get_client() -> PIWebAPIClient:
    global _client
    if _client is None:
        _client = PIWebAPIClient()
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
