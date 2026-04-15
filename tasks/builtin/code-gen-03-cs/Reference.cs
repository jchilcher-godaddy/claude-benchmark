using System;
using System.Collections.Generic;
using System.Linq;

public class LRUCache<TValue>
{
    private readonly int _capacity;
    private readonly Dictionary<string, LinkedListNode<(string Key, TValue Value)>> _cache;
    private readonly LinkedList<(string Key, TValue Value)> _lruList;

    public LRUCache(int capacity)
    {
        if (capacity < 1)
            throw new ArgumentException("Capacity must be at least 1", nameof(capacity));

        _capacity = capacity;
        _cache = new Dictionary<string, LinkedListNode<(string, TValue)>>();
        _lruList = new LinkedList<(string, TValue)>();
    }

    public TValue Get(string key)
    {
        if (!_cache.TryGetValue(key, out var node))
            throw new KeyNotFoundException($"Key '{key}' not found in cache");

        _lruList.Remove(node);
        _lruList.AddFirst(node);

        return node.Value.Value;
    }

    public void Put(string key, TValue value)
    {
        if (_cache.TryGetValue(key, out var existingNode))
        {
            _lruList.Remove(existingNode);
            existingNode.Value = (key, value);
            _lruList.AddFirst(existingNode);
        }
        else
        {
            if (_cache.Count >= _capacity)
            {
                var lruNode = _lruList.Last;
                if (lruNode != null)
                {
                    _cache.Remove(lruNode.Value.Key);
                    _lruList.RemoveLast();
                }
            }

            var newNode = _lruList.AddFirst((key, value));
            _cache[key] = newNode;
        }
    }

    public bool Delete(string key)
    {
        if (!_cache.TryGetValue(key, out var node))
            return false;

        _cache.Remove(key);
        _lruList.Remove(node);
        return true;
    }

    public int Count => _cache.Count;

    public bool ContainsKey(string key) => _cache.ContainsKey(key);

    public List<string> Keys() => _lruList.Select(item => item.Key).ToList();
}
