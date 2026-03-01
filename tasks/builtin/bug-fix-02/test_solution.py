import pytest
from solution import merge_sort


def test_basic_sort():
    assert merge_sort([3, 1, 4, 1, 5, 9, 2, 6]) == [1, 1, 2, 3, 4, 5, 6, 9]


def test_already_sorted():
    assert merge_sort([1, 2, 3, 4, 5]) == [1, 2, 3, 4, 5]


def test_reverse_sorted():
    assert merge_sort([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]


def test_duplicates():
    assert merge_sort([3, 1, 3, 1, 2, 2]) == [1, 1, 2, 2, 3, 3]


def test_stability():
    data = [(1, "a"), (2, "b"), (1, "c"), (2, "d")]
    sorted_data = merge_sort(data)
    assert sorted_data == [(1, "a"), (1, "c"), (2, "b"), (2, "d")]


def test_empty():
    assert merge_sort([]) == []


def test_single_element():
    assert merge_sort([42]) == [42]


def test_original_unchanged():
    original = [3, 1, 4]
    result = merge_sort(original)
    assert original == [3, 1, 4]
    assert result == [1, 3, 4]
