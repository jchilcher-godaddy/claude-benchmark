class LRUCache {
    constructor(capacity) {
        if (capacity < 1) {
            throw new Error("Capacity must be at least 1");
        }
        this.capacity = capacity;
        this.cache = new Map();
    }

    get(key) {
        if (!this.cache.has(key)) {
            throw new Error(`Key not found: ${key}`);
        }
        const value = this.cache.get(key);
        this.cache.delete(key);
        this.cache.set(key, value);
        return value;
    }

    put(key, value) {
        if (this.cache.has(key)) {
            this.cache.delete(key);
        }
        this.cache.set(key, value);
        if (this.cache.size > this.capacity) {
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }
    }

    delete(key) {
        return this.cache.delete(key);
    }

    get length() {
        return this.cache.size;
    }

    has(key) {
        return this.cache.has(key);
    }

    keys() {
        return Array.from(this.cache.keys()).reverse();
    }
}

module.exports = { LRUCache };
