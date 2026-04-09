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


def test_sequence_consistency():
    """Test that fibonacci(n) == fibonacci(n-1) + fibonacci(n-2) for multiple values.

    This catches lookup table implementations that hardcode a few values
    without implementing the actual recurrence relation.
    """
    for n in range(2, 15):
        assert fibonacci(n) == fibonacci(n - 1) + fibonacci(n - 2)


def test_fibonacci_small_values():
    """Test intermediate values between base cases and existing test coverage."""
    assert fibonacci(2) == 1
    assert fibonacci(3) == 2
    assert fibonacci(4) == 3
    assert fibonacci(5) == 5
    assert fibonacci(6) == 8
    assert fibonacci(7) == 13


def test_very_large():
    """Test that the implementation handles large inputs efficiently.

    This verifies an iterative approach rather than naive recursion,
    which would time out on fibonacci(100).
    """
    assert fibonacci(100) == 354224848179261915075


def test_return_type():
    """Test that fibonacci returns an integer, not a float."""
    result = fibonacci(10)
    assert isinstance(result, int)


def test_negative_various():
    """Test that various negative inputs raise ValueError."""
    with pytest.raises(ValueError):
        fibonacci(-5)
    with pytest.raises(ValueError):
        fibonacci(-100)


def test_fibonacci_30():
    """Test an additional intermediate checkpoint."""
    assert fibonacci(30) == 832040
