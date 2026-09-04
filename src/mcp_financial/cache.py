"""A tiny in-memory TTL cache.

yfinance scrapes Yahoo Finance's undocumented endpoints, which rate-limit
aggressively. Tool calls in an MCP session are often repeated for the same
ticker within seconds (e.g. a quote followed by a portfolio calc that
touches the same symbol), so a short-lived cache avoids most 429s without
needing an external cache service.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

T = TypeVar("T")


class TTLCache:
    def __init__(self, ttl_seconds: float = 60.0, maxsize: int = 256):
        self.ttl_seconds = ttl_seconds
        self.maxsize = maxsize
        self._store: dict[Any, tuple[float, Any]] = {}

    def get(self, key: Any) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: Any, value: Any) -> None:
        if len(self._store) >= self.maxsize:
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            self._store.pop(oldest_key, None)
        self._store[key] = (time.monotonic() + self.ttl_seconds, value)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


def ttl_cache(
    ttl_seconds: float = 60.0, maxsize: int = 256
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator version of TTLCache, keyed on the call's args/kwargs."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache = TTLCache(ttl_seconds=ttl_seconds, maxsize=maxsize)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            key = (args, tuple(sorted(kwargs.items())))
            cached = cache.get(key)
            if cached is not None:
                return cached
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        wrapper.cache = cache  # type: ignore[attr-defined]
        return wrapper

    return decorator
