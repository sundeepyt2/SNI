import time

from sni.providers.cache import TTLCache


def test_cache_set_get():
    cache = TTLCache(ttl=60)
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"


def test_cache_miss():
    cache = TTLCache(ttl=60)
    assert cache.get("nonexistent") is None


def test_cache_expiry():
    cache = TTLCache(ttl=1)
    cache.set("key1", "value1")
    time.sleep(1.1)
    assert cache.get("key1") is None


def test_cache_delete():
    cache = TTLCache(ttl=60)
    cache.set("key1", "value1")
    cache.delete("key1")
    assert cache.get("key1") is None


def test_cache_clear():
    cache = TTLCache(ttl=60)
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.clear()
    assert cache.get("key1") is None
    assert cache.get("key2") is None


def test_cache_custom_ttl():
    cache = TTLCache(ttl=60)
    cache.set("key1", "value1", ttl=2)
    time.sleep(1)
    assert cache.get("key1") == "value1"
