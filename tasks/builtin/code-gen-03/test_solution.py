import pytest
from lru_cache import LRUCache


def test_basic_get_put():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    assert cache.get("b") == 2


def test_eviction():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert "a" not in cache
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_access_order():
    cache = LRUCache(3)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    cache.get("a")
    cache.put("d", 4)
    assert "b" not in cache
    assert "a" in cache


def test_update_existing():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("a", 10)
    cache.put("c", 3)
    assert "b" not in cache
    assert cache.get("a") == 10


def test_delete():
    cache = LRUCache(2)
    cache.put("a", 1)
    assert cache.delete("a") is True
    assert "a" not in cache
    assert cache.delete("a") is False


def test_len():
    cache = LRUCache(3)
    assert len(cache) == 0
    cache.put("a", 1)
    assert len(cache) == 1
    cache.put("b", 2)
    assert len(cache) == 2
    cache.put("c", 3)
    cache.put("d", 4)
    assert len(cache) == 3


def test_contains():
    cache = LRUCache(2)
    cache.put("a", 1)
    assert "a" in cache
    assert "b" not in cache


def test_keys_mru_order():
    cache = LRUCache(3)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert cache.keys() == ["c", "b", "a"]
    cache.get("a")
    assert cache.keys() == ["a", "c", "b"]


def test_capacity_one():
    cache = LRUCache(1)
    cache.put("a", 1)
    cache.put("b", 2)
    assert "a" not in cache
    assert cache.get("b") == 2


def test_invalid_capacity():
    with pytest.raises(ValueError):
        LRUCache(0)
    with pytest.raises(ValueError):
        LRUCache(-1)


def test_get_nonexistent():
    cache = LRUCache(2)
    with pytest.raises(KeyError):
        cache.get("missing")
