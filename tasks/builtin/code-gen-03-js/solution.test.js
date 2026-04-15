const { LRUCache } = require('./lru_cache');

test('constructor with valid capacity', () => {
    const cache = new LRUCache(3);
    expect(cache.length).toBe(0);
});

test('constructor with invalid capacity throws', () => {
    expect(() => new LRUCache(0)).toThrow();
    expect(() => new LRUCache(-1)).toThrow();
});

test('put and get single item', () => {
    const cache = new LRUCache(2);
    cache.put('a', 1);
    expect(cache.get('a')).toBe(1);
    expect(cache.length).toBe(1);
});

test('put updates existing key', () => {
    const cache = new LRUCache(2);
    cache.put('a', 1);
    cache.put('a', 2);
    expect(cache.get('a')).toBe(2);
    expect(cache.length).toBe(1);
});

test('get on missing key throws', () => {
    const cache = new LRUCache(2);
    expect(() => cache.get('missing')).toThrow();
});

test('evicts LRU item at capacity', () => {
    const cache = new LRUCache(2);
    cache.put('a', 1);
    cache.put('b', 2);
    cache.put('c', 3);
    expect(cache.has('a')).toBe(false);
    expect(cache.has('b')).toBe(true);
    expect(cache.has('c')).toBe(true);
    expect(cache.length).toBe(2);
});

test('get marks item as recently used', () => {
    const cache = new LRUCache(2);
    cache.put('a', 1);
    cache.put('b', 2);
    cache.get('a');
    cache.put('c', 3);
    expect(cache.has('a')).toBe(true);
    expect(cache.has('b')).toBe(false);
    expect(cache.has('c')).toBe(true);
});

test('put marks item as recently used', () => {
    const cache = new LRUCache(2);
    cache.put('a', 1);
    cache.put('b', 2);
    cache.put('a', 10);
    cache.put('c', 3);
    expect(cache.has('a')).toBe(true);
    expect(cache.has('b')).toBe(false);
    expect(cache.has('c')).toBe(true);
});

test('delete removes item', () => {
    const cache = new LRUCache(2);
    cache.put('a', 1);
    expect(cache.delete('a')).toBe(true);
    expect(cache.has('a')).toBe(false);
    expect(cache.length).toBe(0);
});

test('delete returns false for missing key', () => {
    const cache = new LRUCache(2);
    expect(cache.delete('missing')).toBe(false);
});

test('has returns correct values', () => {
    const cache = new LRUCache(2);
    cache.put('a', 1);
    expect(cache.has('a')).toBe(true);
    expect(cache.has('b')).toBe(false);
});

test('keys returns MRU order', () => {
    const cache = new LRUCache(3);
    cache.put('a', 1);
    cache.put('b', 2);
    cache.put('c', 3);
    expect(cache.keys()).toEqual(['c', 'b', 'a']);
});

test('keys updates after get', () => {
    const cache = new LRUCache(3);
    cache.put('a', 1);
    cache.put('b', 2);
    cache.put('c', 3);
    cache.get('a');
    expect(cache.keys()).toEqual(['a', 'c', 'b']);
});

test('complex sequence', () => {
    const cache = new LRUCache(3);
    cache.put('a', 1);
    cache.put('b', 2);
    cache.put('c', 3);
    expect(cache.get('a')).toBe(1);
    cache.put('d', 4);
    expect(cache.has('b')).toBe(false);
    cache.put('e', 5);
    expect(cache.has('c')).toBe(false);
    expect(cache.keys()).toEqual(['e', 'd', 'a']);
});

test('capacity of 1', () => {
    const cache = new LRUCache(1);
    cache.put('a', 1);
    cache.put('b', 2);
    expect(cache.has('a')).toBe(false);
    expect(cache.has('b')).toBe(true);
    expect(cache.length).toBe(1);
});
