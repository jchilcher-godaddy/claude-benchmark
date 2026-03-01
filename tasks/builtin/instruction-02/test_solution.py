"""Tests for instruction-02 task."""

import inspect
import logging
import re

import pytest

from solution import calculate_shipping


def test_standard_shipping_basic():
    """Test standard shipping calculation."""
    order = {
        "weight_kg": 10,
        "distance_km": 100,
        "order_total": 50,
        "shipping_type": "standard",
    }
    result = calculate_shipping(order)
    assert result["base_cost"] == 5
    assert result["weight_cost"] == 5.0
    assert result["distance_cost"] == 1.0
    assert result["total_cost"] == 11.0
    assert result["free_shipping"] is False


def test_express_shipping():
    """Test express shipping is 2x standard."""
    order = {
        "weight_kg": 10,
        "distance_km": 100,
        "order_total": 50,
        "shipping_type": "express",
    }
    result = calculate_shipping(order)
    assert result["total_cost"] == 22.0
    assert result["free_shipping"] is False


def test_overnight_shipping():
    """Test overnight shipping is 3x standard."""
    order = {
        "weight_kg": 10,
        "distance_km": 100,
        "order_total": 50,
        "shipping_type": "overnight",
    }
    result = calculate_shipping(order)
    assert result["total_cost"] == 33.0
    assert result["free_shipping"] is False


def test_free_standard_shipping():
    """Test free standard shipping for orders over $100."""
    order = {
        "weight_kg": 10,
        "distance_km": 100,
        "order_total": 150,
        "shipping_type": "standard",
    }
    result = calculate_shipping(order)
    assert result["total_cost"] == 0
    assert result["free_shipping"] is True


def test_no_free_express_shipping():
    """Test express shipping not free even for orders over $100."""
    order = {
        "weight_kg": 10,
        "distance_km": 100,
        "order_total": 150,
        "shipping_type": "express",
    }
    result = calculate_shipping(order)
    assert result["total_cost"] == 22.0
    assert result["free_shipping"] is False


def test_no_free_overnight_shipping():
    """Test overnight shipping not free even for orders over $100."""
    order = {
        "weight_kg": 10,
        "distance_km": 100,
        "order_total": 150,
        "shipping_type": "overnight",
    }
    result = calculate_shipping(order)
    assert result["total_cost"] == 33.0
    assert result["free_shipping"] is False


def test_missing_field_raises_valueerror():
    """Test missing required field raises ValueError."""
    order = {"weight_kg": 10, "distance_km": 100}
    with pytest.raises(ValueError) as exc_info:
        calculate_shipping(order)
    assert "order_total" in str(exc_info.value).lower() or "shipping_type" in str(exc_info.value).lower()


def test_invalid_shipping_type_raises_valueerror():
    """Test invalid shipping type raises ValueError."""
    order = {
        "weight_kg": 10,
        "distance_km": 100,
        "order_total": 50,
        "shipping_type": "invalid",
    }
    with pytest.raises(ValueError) as exc_info:
        calculate_shipping(order)
    assert "shipping_type" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()


def test_negative_weight_raises_valueerror():
    """Test negative weight raises ValueError."""
    order = {
        "weight_kg": -5,
        "distance_km": 100,
        "order_total": 50,
        "shipping_type": "standard",
    }
    with pytest.raises(ValueError) as exc_info:
        calculate_shipping(order)
    assert "weight" in str(exc_info.value).lower()


def test_negative_distance_raises_valueerror():
    """Test negative distance raises ValueError."""
    order = {
        "weight_kg": 10,
        "distance_km": -50,
        "order_total": 50,
        "shipping_type": "standard",
    }
    with pytest.raises(ValueError) as exc_info:
        calculate_shipping(order)
    assert "distance" in str(exc_info.value).lower()


def test_returns_json_serializable_dict():
    """Test function returns JSON-serializable dict."""
    import json

    order = {
        "weight_kg": 10,
        "distance_km": 100,
        "order_total": 50,
        "shipping_type": "standard",
    }
    result = calculate_shipping(order)
    assert isinstance(result, dict)
    json.dumps(result)


def test_no_bare_except():
    """Test code does not use bare except or except Exception."""
    import solution

    source = inspect.getsource(solution)
    assert "except:" not in source or "except Exception:" not in source, "Code uses bare except or except Exception"


def test_uses_logging_not_print():
    """Test code uses logging module, not print()."""
    import solution

    source = inspect.getsource(solution)
    print_pattern = r'\bprint\s*\('
    assert not re.search(print_pattern, source), "Code uses print() instead of logging"


def test_has_module_level_constants():
    """Test magic numbers are defined as module-level UPPER_CASE constants."""
    import solution

    has_uppercase_constant = False
    for name in dir(solution):
        if name.isupper() and not name.startswith("_"):
            has_uppercase_constant = True
            break
    assert has_uppercase_constant, "No module-level UPPER_CASE constants found"


def test_exact_free_shipping_threshold():
    """Test order exactly at $100 threshold."""
    order = {
        "weight_kg": 10,
        "distance_km": 100,
        "order_total": 100,
        "shipping_type": "standard",
    }
    result = calculate_shipping(order)
    assert result["free_shipping"] is False


def test_zero_weight_and_distance():
    """Test zero weight and distance."""
    order = {
        "weight_kg": 0,
        "distance_km": 0,
        "order_total": 50,
        "shipping_type": "standard",
    }
    result = calculate_shipping(order)
    assert result["base_cost"] == 5
    assert result["weight_cost"] == 0
    assert result["distance_cost"] == 0
    assert result["total_cost"] == 5.0
