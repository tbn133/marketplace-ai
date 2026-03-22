"""In-memory cache implementation. Implements CachePort.

Used as fallback when Redis is not available (local mode).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class _CacheEntry:
    value: str
    expires_at: float | None = None

    @property
    def expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.monotonic() > self.expires_at


class MemoryCache:
    def __init__(self, default_ttl: int = 300):
        self._store: dict[str, _CacheEntry] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expired:
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: str, ttl: int | None = None) -> None:
        t = ttl if ttl is not None else self._default_ttl
        expires_at = time.monotonic() + t if t > 0 else None
        self._store[key] = _CacheEntry(value=value, expires_at=expires_at)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
