"""
Async-safe in-process LRU cache with per-entry TTL.

No external dependencies.  Designed for a small number of concurrent
users (5-10) where a single async event loop services all requests.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Optional

from config import config

logger = logging.getLogger(__name__)


class TTLCache:
    """
    Fixed-capacity async cache.

    Entries expire after their individual TTL.  When capacity is
    exceeded the oldest entries are evicted (approximated by iteration
    order of the underlying dict, which is insertion-ordered in CPython).
    """

    def __init__(self, max_size: int = 500) -> None:
        self._store: dict[str, tuple[Any, float]] = {}  # key → (value, expiry)
        self._lock = asyncio.Lock()
        self._max_size = max_size
        self.hits = 0
        self.misses = 0

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def get(self, key: str) -> Optional[Any]:
        if not config.cache.enabled:
            return None
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None
            value, expiry = entry
            if time.monotonic() > expiry:
                del self._store[key]
                self.misses += 1
                return None
            self.hits += 1
            return value

    async def set(self, key: str, value: Any, ttl: int) -> None:
        if not config.cache.enabled or ttl <= 0:
            return
        async with self._lock:
            if len(self._store) >= self._max_size:
                self._evict_expired()
            if len(self._store) >= self._max_size:
                # Remove oldest entry
                oldest = next(iter(self._store))
                del self._store[oldest]
            self._store[key] = (value, time.monotonic() + ttl)

    async def invalidate(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    def stats(self) -> dict[str, Any]:
        total = self.hits + self.misses
        return {
            "size": len(self._store),
            "max_size": self._max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 3) if total else 0.0,
        }

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]

    # ------------------------------------------------------------------ #
    # Key builders
    # ------------------------------------------------------------------ #

    @staticmethod
    def make_key(tool: str, params: dict[str, Any]) -> str:
        raw = f"{tool}::{json.dumps(params, sort_keys=True, default=str)}"
        return hashlib.sha1(raw.encode()).hexdigest()


# --------------------------------------------------------------------------- #
# TTL constants by tool category (seconds)
# --------------------------------------------------------------------------- #

class TTL:
    CURRENT_VALUE: int = config.cache.current_value_ttl    # 30 s
    SUMMARY: int = config.cache.summary_ttl                 # 5 min
    HEALTH: int = config.cache.health_ttl                   # 60 s
    STRUCTURAL: int = config.cache.structural_ttl           # 10 min (graph)
    RESOLUTION: int = config.cache.resolution_ttl           # 15 min
    FORECAST: int = config.cache.forecast_ttl               # 1 h


# Module-level singleton
_cache: Optional[TTLCache] = None


def get_cache() -> TTLCache:
    global _cache
    if _cache is None:
        _cache = TTLCache(max_size=config.cache.max_size)
    return _cache
