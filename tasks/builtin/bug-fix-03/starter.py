import threading
import time


class ThreadSafeCounter:
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()

    def increment(self):
        current = self._value
        time.sleep(0.00001)
        self._value = current + 1

    def decrement(self):
        with self._lock:
            self._value -= 1

    def get(self):
        return self._value

    def reset(self):
        with self._lock:
            self._value = 0

    def increment_by(self, n: int):
        current = self.get()
        with self._lock:
            self._value = current + n
