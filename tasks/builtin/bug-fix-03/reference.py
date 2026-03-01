import threading


class ThreadSafeCounter:
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:
            self._value += 1

    def decrement(self):
        with self._lock:
            self._value -= 1

    def get(self):
        with self._lock:
            return self._value

    def reset(self):
        with self._lock:
            self._value = 0

    def increment_by(self, n: int):
        with self._lock:
            self._value += n
