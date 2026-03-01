import pytest
from solution import binary_search


def test_first_element():
    assert binary_search([1, 2, 3, 4, 5], 1) == 0


def test_last_element():
    assert binary_search([1, 2, 3, 4, 5], 5) == 4


def test_middle_element():
    assert binary_search([1, 2, 3, 4, 5], 3) == 2


def test_not_present():
    assert binary_search([1, 2, 3, 4, 5], 6) == -1


def test_empty_list():
    assert binary_search([], 1) == -1


def test_single_element_found():
    assert binary_search([5], 5) == 0


def test_single_element_not_found():
    assert binary_search([5], 3) == -1


def test_two_elements():
    assert binary_search([1, 3], 1) == 0
    assert binary_search([1, 3], 3) == 1
