"""TTL in-memory cache for odds aggregator HTTP responses.

Used to avoid burning TheOddsAPI quota (500 req/month free). Each
(url, source) key is cached for `ttl_seconds`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class _CacheEntry:
    value: object
    timestamp: float


class TtlCache:
    """In-memory TTL cache for HTTP responses."""

    def __init__(self, ttl_seconds: int = 60) -> None:
        self._ttl = ttl_seconds
        self._store: dict[tuple[str, str], _CacheEntry] = {}

    def get(self, source: str, url: str) -> object | None:
        key = (source, url)
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry.timestamp > self._ttl:
            del self._store[key]
            return None
        return entry.value

    def set(self, source: str, url: str, value: object) -> None:
        self._store[(source, url)] = _CacheEntry(
            value=value, timestamp=time.monotonic()
        )

    def clear(self) -> None:
        self._store.clear()
