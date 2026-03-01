"""Tests for refactor-02 task."""

import pytest

from solution import validate_and_process_order


def test_valid_order_no_discount():
    """Test valid order without discounts."""
    order = {
        "items": [
            {"price": 10.0, "quantity": 2},
            {"price": 5.0, "quantity": 3},
        ]
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["subtotal"] == 35.0
    assert result["discount"] == 0
    assert result["total"] == 35.0


def test_valid_order_with_premium_customer():
    """Test valid order with premium customer discount."""
    order = {
        "items": [{"price": 100.0, "quantity": 1}],
        "customer_type": "premium",
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["subtotal"] == 100.0
    assert result["discount"] == 15.0
    assert result["total"] == 85.0


def test_valid_order_with_regular_customer():
    """Test valid order with regular customer discount."""
    order = {
        "items": [{"price": 100.0, "quantity": 1}],
        "customer_type": "regular",
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["subtotal"] == 100.0
    assert result["discount"] == 5.0
    assert result["total"] == 95.0


def test_valid_order_with_save20_coupon():
    """Test valid order with SAVE20 coupon."""
    order = {
        "items": [{"price": 100.0, "quantity": 1}],
        "coupon_code": "SAVE20",
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["subtotal"] == 100.0
    assert result["discount"] == 20.0
    assert result["total"] == 80.0


def test_valid_order_with_save10_coupon():
    """Test valid order with SAVE10 coupon."""
    order = {
        "items": [{"price": 100.0, "quantity": 1}],
        "coupon_code": "SAVE10",
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["subtotal"] == 100.0
    assert result["discount"] == 10.0
    assert result["total"] == 90.0


def test_coupon_overrides_lower_customer_discount():
    """Test that higher coupon discount overrides lower customer discount."""
    order = {
        "items": [{"price": 100.0, "quantity": 1}],
        "customer_type": "regular",
        "coupon_code": "SAVE20",
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["discount"] == 20.0


def test_customer_discount_used_when_higher_than_coupon():
    """Test that customer discount is used when higher than coupon."""
    order = {
        "items": [{"price": 100.0, "quantity": 1}],
        "customer_type": "premium",
        "coupon_code": "SAVE10",
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["discount"] == 15.0


def test_missing_items_field():
    """Test order missing items field."""
    order = {"customer_type": "regular"}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Order must have items field"


def test_empty_items():
    """Test order with empty items list."""
    order = {"items": []}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Order must contain at least one item"


def test_items_not_dicts():
    """Test order with non-dict items."""
    order = {"items": ["item1", "item2"]}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Items must be dictionaries"


def test_items_missing_price():
    """Test order with items missing price."""
    order = {"items": [{"quantity": 1}]}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Items must have price and quantity"


def test_items_missing_quantity():
    """Test order with items missing quantity."""
    order = {"items": [{"price": 10.0}]}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Items must have price and quantity"


def test_zero_quantity():
    """Test order with zero quantity."""
    order = {"items": [{"price": 10.0, "quantity": 0}]}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Item quantities must be positive"


def test_negative_quantity():
    """Test order with negative quantity."""
    order = {"items": [{"price": 10.0, "quantity": -1}]}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Item quantities must be positive"


def test_negative_price():
    """Test order with negative price."""
    order = {"items": [{"price": -10.0, "quantity": 1}]}
    result = validate_and_process_order(order)
    assert result["valid"] is False
    assert result["error"] == "Item prices must be non-negative"


def test_zero_price():
    """Test order with zero price (should be valid)."""
    order = {"items": [{"price": 0.0, "quantity": 1}]}
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["subtotal"] == 0.0


def test_multiple_items():
    """Test order with multiple items and complex pricing."""
    order = {
        "items": [
            {"price": 10.0, "quantity": 2},
            {"price": 15.0, "quantity": 1},
            {"price": 5.0, "quantity": 4},
        ],
        "customer_type": "premium",
        "coupon_code": "SAVE10",
    }
    result = validate_and_process_order(order)
    assert result["valid"] is True
    assert result["subtotal"] == 55.0
    assert result["discount"] == 8.25
    assert result["total"] == 46.75
