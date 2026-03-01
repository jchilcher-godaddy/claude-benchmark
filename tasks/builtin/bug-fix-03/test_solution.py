import pytest
from concurrent.futures import ThreadPoolExecutor
from solution import ThreadSafeCounter


def test_basic_increment():
    counter = ThreadSafeCounter()
    counter.increment()
    assert counter.get() == 1


def test_basic_decrement():
    counter = ThreadSafeCounter()
    counter.increment()
    counter.increment()
    counter.decrement()
    assert counter.get() == 1


def test_reset():
    counter = ThreadSafeCounter()
    counter.increment()
    counter.increment()
    counter.reset()
    assert counter.get() == 0


def test_increment_by():
    counter = ThreadSafeCounter()
    counter.increment_by(5)
    assert counter.get() == 5


def test_concurrent_increments():
    counter = ThreadSafeCounter()
    num_threads = 20
    increments_per_thread = 5000

    def worker():
        for _ in range(increments_per_thread):
            counter.increment()

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker) for _ in range(num_threads)]
        for future in futures:
            future.result()

    expected = num_threads * increments_per_thread
    assert counter.get() == expected


def test_concurrent_mixed_operations():
    counter = ThreadSafeCounter()
    num_threads = 10
    operations_per_thread = 2000

    def worker_increment():
        for _ in range(operations_per_thread):
            counter.increment()

    def worker_decrement():
        for _ in range(operations_per_thread):
            counter.decrement()

    def worker_increment_by():
        for _ in range(operations_per_thread // 10):
            counter.increment_by(10)

    with ThreadPoolExecutor(max_workers=num_threads * 3) as executor:
        futures = []
        for _ in range(num_threads):
            futures.append(executor.submit(worker_increment))
            futures.append(executor.submit(worker_decrement))
            futures.append(executor.submit(worker_increment_by))

        for future in futures:
            future.result()

    expected = num_threads * operations_per_thread
    assert counter.get() == expected
