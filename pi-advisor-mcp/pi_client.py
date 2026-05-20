"""
Async PI Web API client.

Handles authentication, session management, connection pooling, retries,
and provides convenience wrappers with selectedFields support to minimise
response payloads.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import ssl
import time
from typing import Any, Dict, List, Optional

import aiohttp

from config import config

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


def _build_auth_header(username: str, password: str) -> str:
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {creds}"


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

    # ------------------------------------------------------------------ #
    # Session lifecycle
    # ------------------------------------------------------------------ #

    def _build_ssl_ctx(self) -> ssl.SSLContext | bool:
        if not config.pi.verify_ssl:
            return False
        ctx = ssl.create_default_context()
        return ctx

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
        if cfg.auth_method == "basic" and cfg.username and cfg.password:
            headers["Authorization"] = _build_auth_header(cfg.username, cfg.password)
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
                async with session.request(method, url, params=params, json=json) as resp:
                    if resp.status in _RETRYABLE_STATUSES:
                        wait = 2 ** attempt
                        logger.warning("PI API %s %s → %d, retry in %ds", method, path, resp.status, wait)
                        await asyncio.sleep(wait)
                        continue
                    if resp.status == 401:
                        raise PermissionError(f"PI Web API 401 — check credentials ({path})")
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
            "links": list((data.get("Links") or {}).keys()),
        }

    # ---- Asset Framework -------------------------------------------------

    async def get_af_servers(self) -> List[Dict]:
        data = await self.get("/assetservers")
        return data.get("Items", [])

    async def get_af_databases(self, server_webid: str) -> List[Dict]:
        data = await self.get(f"/assetservers/{server_webid}/assetdatabases")
        return data.get("Items", [])

    async def search_elements(
        self,
        database_webid: str,
        query: str = "*",
        *,
        template_name: str = "",
        max_count: int = 1000,
        selected_fields: str = "Items.WebId,Items.Name,Items.Description,Items.Path,Items.TemplateName,Items.HasChildren",
    ) -> List[Dict]:
        params: Dict[str, Any] = {
            "query": f"Name:={query}",
            "maxCount": max_count,
            "selectedFields": selected_fields,
        }
        if template_name:
            params["templateName"] = template_name
        data = await self.get(f"/assetdatabases/{database_webid}/elementssearch", params=params)
        return data.get("Items", [])

    async def get_element_children(
        self,
        element_webid: str,
        selected_fields: str = "Items.WebId,Items.Name,Items.Description,Items.Path,Items.TemplateName,Items.HasChildren",
    ) -> List[Dict]:
        data = await self.get(
            f"/elements/{element_webid}/elements",
            params={"selectedFields": selected_fields},
        )
        return data.get("Items", [])

    async def get_element_attributes(
        self,
        element_webid: str,
        max_count: int = 100,
        selected_fields: str = (
            "Items.WebId,Items.Name,Items.Description,Items.Type,"
            "Items.DefaultUnitsName,Items.DataReference"
        ),
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
        selected_fields: str = "Timestamp,Value,UnitsAbbreviation,Good",
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
        selected_fields: str = "Items.Timestamp,Items.Value,Items.Good",
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
        selected_fields: str = "Items.Timestamp,Items.Value,Items.Good",
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
        selected_fields: str = "Items.Type,Items.Value.Value,Items.Value.Timestamp",
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
        selected_fields: str = "Items.WebId,Items.Name,Items.Value,Items.Timestamp,Items.Good",
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
        selected_fields: str = "Items.WebId,Items.Name,Items.Descriptor,Items.EngineeringUnits",
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
