import pytest
from solution import fibonacci


def test_base_case_zero():
    assert fibonacci(0) == 0


def test_base_case_one():
    assert fibonacci(1) == 1


def test_small_fibonacci():
    assert fibonacci(10) == 55


def test_larger_fibonacci():
    assert fibonacci(20) == 6765


def test_negative_raises_error():
    with pytest.raises(ValueError):
        fibonacci(-1)


def test_large_fibonacci():
    assert fibonacci(50) == 12586269025
