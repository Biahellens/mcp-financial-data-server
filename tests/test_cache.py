"""Unit tests for the TTL cache used to avoid yfinance rate limits."""

from __future__ import annotations

from mcp_financial.cache import TTLCache, ttl_cache


def test_ttl_cache_returns_cached_value_before_expiry():
    cache = TTLCache(ttl_seconds=60)
    cache.set("key", "value")
    assert cache.get("key") == "value"


def test_ttl_cache_expires_after_ttl(monkeypatch):
    import time

    cache = TTLCache(ttl_seconds=10)
    fake_now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])

    cache.set("key", "value")
    assert cache.get("key") == "value"

    fake_now[0] += 11  # past the 10s TTL
    assert cache.get("key") is None


def test_ttl_cache_evicts_oldest_when_full():
    cache = TTLCache(ttl_seconds=60, maxsize=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)  # should evict "a", the oldest
    assert len(cache) == 2
    assert cache.get("a") is None
    assert cache.get("c") == 3


def test_ttl_cache_decorator_avoids_repeated_calls():
    calls = []

    @ttl_cache(ttl_seconds=60)
    def expensive(x):
        calls.append(x)
        return x * 2

    assert expensive(3) == 6
    assert expensive(3) == 6
    assert calls == [3]  # second call was served from cache


def test_ttl_cache_decorator_distinguishes_arguments():
    @ttl_cache(ttl_seconds=60)
    def identity(x):
        return x

    assert identity(1) == 1
    assert identity(2) == 2
