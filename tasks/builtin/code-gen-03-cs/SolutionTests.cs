using Xunit;
using System;
using System.Collections.Generic;
using System.Linq;

public class LRUCacheTests
{
    [Fact]
    public void InvalidCapacityThrows()
    {
        Assert.Throws<ArgumentException>(() => new LRUCache<int>(0));
        Assert.Throws<ArgumentException>(() => new LRUCache<int>(-1));
    }

    [Fact]
    public void BasicPutAndGet()
    {
        var cache = new LRUCache<int>(2);
        cache.Put("a", 1);
        Assert.Equal(1, cache.Get("a"));
    }

    [Fact]
    public void GetNonExistentKeyThrows()
    {
        var cache = new LRUCache<int>(2);
        Assert.Throws<KeyNotFoundException>(() => cache.Get("missing"));
    }

    [Fact]
    public void EvictsLRUWhenAtCapacity()
    {
        var cache = new LRUCache<int>(2);
        cache.Put("a", 1);
        cache.Put("b", 2);
        cache.Put("c", 3);

        Assert.False(cache.ContainsKey("a"));
        Assert.Equal(2, cache.Get("b"));
        Assert.Equal(3, cache.Get("c"));
    }

    [Fact]
    public void UpdateExistingKeyRefreshesLRU()
    {
        var cache = new LRUCache<int>(2);
        cache.Put("a", 1);
        cache.Put("b", 2);
        cache.Put("a", 10);
        cache.Put("c", 3);

        Assert.False(cache.ContainsKey("b"));
        Assert.Equal(10, cache.Get("a"));
        Assert.Equal(3, cache.Get("c"));
    }

    [Fact]
    public void GetRefreshesLRU()
    {
        var cache = new LRUCache<int>(2);
        cache.Put("a", 1);
        cache.Put("b", 2);
        cache.Get("a");
        cache.Put("c", 3);

        Assert.True(cache.ContainsKey("a"));
        Assert.False(cache.ContainsKey("b"));
        Assert.Equal(3, cache.Get("c"));
    }

    [Fact]
    public void DeleteRemovesKey()
    {
        var cache = new LRUCache<int>(2);
        cache.Put("a", 1);
        Assert.True(cache.Delete("a"));
        Assert.False(cache.ContainsKey("a"));
    }

    [Fact]
    public void DeleteNonExistentReturnsFalse()
    {
        var cache = new LRUCache<int>(2);
        Assert.False(cache.Delete("missing"));
    }

    [Fact]
    public void CountReflectsSize()
    {
        var cache = new LRUCache<int>(3);
        Assert.Equal(0, cache.Count);

        cache.Put("a", 1);
        Assert.Equal(1, cache.Count);

        cache.Put("b", 2);
        Assert.Equal(2, cache.Count);

        cache.Delete("a");
        Assert.Equal(1, cache.Count);
    }

    [Fact]
    public void ContainsKeyWorks()
    {
        var cache = new LRUCache<int>(2);
        cache.Put("a", 1);
        Assert.True(cache.ContainsKey("a"));
        Assert.False(cache.ContainsKey("b"));
    }

    [Fact]
    public void KeysReturnsMRUOrder()
    {
        var cache = new LRUCache<int>(3);
        cache.Put("a", 1);
        cache.Put("b", 2);
        cache.Put("c", 3);

        var keys = cache.Keys();
        Assert.Equal(new[] { "c", "b", "a" }, keys);
    }

    [Fact]
    public void KeysReflectsGetOrder()
    {
        var cache = new LRUCache<int>(3);
        cache.Put("a", 1);
        cache.Put("b", 2);
        cache.Put("c", 3);
        cache.Get("a");

        var keys = cache.Keys();
        Assert.Equal("a", keys[0]);
    }

    [Fact]
    public void CapacityOne()
    {
        var cache = new LRUCache<int>(1);
        cache.Put("a", 1);
        cache.Put("b", 2);

        Assert.False(cache.ContainsKey("a"));
        Assert.Equal(2, cache.Get("b"));
    }

    [Fact]
    public void WorksWithStringValues()
    {
        var cache = new LRUCache<string>(2);
        cache.Put("key1", "value1");
        cache.Put("key2", "value2");

        Assert.Equal("value1", cache.Get("key1"));
        Assert.Equal("value2", cache.Get("key2"));
    }
}
