from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity: int):
        if capacity < 1:
            raise ValueError("Capacity must be at least 1")
        self.capacity = capacity
        self.cache = OrderedDict()

    def get(self, key: str):
        if key not in self.cache:
            raise KeyError(key)
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def delete(self, key: str) -> bool:
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def __len__(self):
        return len(self.cache)

    def __contains__(self, key: str):
        return key in self.cache

    def keys(self) -> list[str]:
        return list(reversed(self.cache.keys()))
